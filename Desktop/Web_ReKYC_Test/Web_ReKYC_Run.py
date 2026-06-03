import builtins
import datetime
import html
import json
import os
import smtplib
import subprocess
import sys
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from Web_ReKYC_Config import EMAIL_REPORT
from teams_reporter import send_teams_report


_original_print = builtins.print


def print(*args, **kwargs):
    safe_args = [str(arg).encode("ascii", "replace").decode("ascii") for arg in args]
    _original_print(*safe_args, **kwargs)


def send_report(status, video_path, log_lines, step_results, duration):
    receivers = EMAIL_REPORT["receiver"]
    if isinstance(receivers, str):
        receivers = [receivers]

    color = "#16a34a" if status == "PASS" else "#dc2626"
    now = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    subject = f"Web ReKYC Automation Report - {status} | {now}"

    step_rows = ""
    for step in step_results:
        row_color = "#d1fae5" if step["status"] == "PASS" else "#fee2e2"
        step_rows += f"""
        <tr style="background:{row_color}">
            <td style="padding:10px;border:1px solid #d1d5db">{step["step"]}</td>
            <td style="padding:10px;border:1px solid #d1d5db;font-weight:700;color:{color}">{step["status"]}</td>
            <td style="padding:10px;border:1px solid #d1d5db">{html.escape(step.get("name", ""))}</td>
            <td style="padding:10px;border:1px solid #d1d5db">{html.escape(step.get("reason", ""))}</td>
        </tr>
        """

    body = f"""
    <html>
    <body style="margin:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#111827">
        <div style="max-width:1080px;margin:0 auto;padding:20px">
            <div style="background:#ffffff;border:1px solid #e5e7eb">
                <div style="background:#1f3f68;color:#ffffff;padding:22px 24px">
                    <div style="font-size:22px;font-weight:700">Web ReKYC Automation Report</div>
                    <div style="font-size:13px;margin-top:6px">Generated: {now} | Duration: {duration}</div>
                </div>
                <div style="padding:18px 24px 24px">
                    <div style="font-size:14px;font-weight:700;margin-bottom:14px">
                        Code Review: PASS &nbsp;|&nbsp; Test Execution:
                        <span style="background:{'#dcfce7' if status == 'PASS' else '#fee2e2'};color:{color};padding:7px 18px;border-radius:5px">{status}</span>
                    </div>
                    <table style="width:100%;border-collapse:collapse;font-size:13px">
                        <thead>
                            <tr style="background:#344153;color:#ffffff;text-align:left">
                                <th style="padding:10px;border:1px solid #4b5563">Step</th>
                                <th style="padding:10px;border:1px solid #4b5563">Status</th>
                                <th style="padding:10px;border:1px solid #4b5563">Name</th>
                                <th style="padding:10px;border:1px solid #4b5563">Reason</th>
                            </tr>
                        </thead>
                        <tbody>{step_rows}</tbody>
                    </table>
                    <div style="font-size:12px;color:#4b5563;margin-top:14px">
                        Video: {"Attached" if video_path else "No video recording found"}
                        {f"<br>Video File: {html.escape(video_path)}" if video_path else ""}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_REPORT["sender"]
    msg["To"] = ", ".join(receivers)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    if video_path and os.path.exists(video_path):
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb <= 20:
            with open(video_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(video_path)}"',
            )
            msg.attach(part)
            print(f"Video attached: {os.path.basename(video_path)}")
        else:
            print("Video too large, skipped")

    try:
        server = smtplib.SMTP_SSL(EMAIL_REPORT["smtp_server"], EMAIL_REPORT["smtp_port"])
        smtp_username = EMAIL_REPORT.get("username", EMAIL_REPORT["sender"])
        server.login(smtp_username, EMAIL_REPORT["password"])
        server.sendmail(EMAIL_REPORT["sender"], receivers, msg.as_string())
        server.quit()
        print("Mail sent successfully")
        send_teams_report(
            title=subject,
            status=status,
            html_body=body,
            video_path=video_path,
            step_results=step_results,
            duration=duration,
            flow_details={"report_name": "Web ReKYC Automation Report"},
        )
    except Exception as e:
        print("Mail failed:", e)


def find_latest_video():
    base_dir = os.path.dirname(__file__)
    search_roots = [
        os.path.join(base_dir, "videos"),
        os.path.join(base_dir, "test-results"),
    ]
    videos = []
    for root in search_roots:
        if os.path.exists(root):
            for current_root, _, files in os.walk(root):
                for file_name in files:
                    if file_name.lower().endswith(".webm"):
                        videos.append(os.path.join(current_root, file_name))
    if not videos:
        return None

    return max(videos, key=os.path.getmtime)


if __name__ == "__main__":
    print("Starting Web ReKYC Test...")
    start_time = time.time()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/Web_ReKYC_Test.py",
            "-v",
            "--tb=short",
            "--headed",
            "--video=on",
            "--output=videos",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    elapsed = int(time.time() - start_time)
    duration = f"{elapsed // 60}m {elapsed % 60}s"

    output = result.stdout + result.stderr
    log_lines = output.splitlines()
    print(output)

    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\nTest Result: {status} | Duration: {duration}")

    step_results = []
    json_path = os.path.join(os.path.dirname(__file__), "web_rekyc_step_results.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    step_results = json.loads(content)
                    print(f"Loaded {len(step_results)} step results")
        except Exception as e:
            print(f"Could not read json: {e}")

    video_path = find_latest_video()
    if video_path:
        print(f"Video found: {video_path}")

    print("\nSending email report...")
    send_report(
        status=status,
        video_path=video_path,
        log_lines=log_lines,
        step_results=step_results,
        duration=duration,
    )
    sys.exit(result.returncode)
