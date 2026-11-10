#!/usr/bin/env python3
"""发邮件（SMTP，Python 标准库，无需安装任何东西）。

配置从环境变量读取（或从加密凭据库注入）：
  SMTP_HOST   例 smtp.qq.com
  SMTP_PORT   例 465（SSL）或 587（STARTTLS）
  SMTP_USER   登录账号（通常是完整邮箱）
  SMTP_PASS   授权码（不是登录密码）
  MAIL_FROM   发件人显示地址（默认同 SMTP_USER）

用法：
  python3 send-mail.py --to a@b.com --subject "主题" --body "正文"
  python3 send-mail.py --to a@b.com --subject "报表" --body "见附件" --attach /path/report.pdf
  python3 send-mail.py --check        # 只测试 SMTP 登录

常用服务商：
  QQ 邮箱      smtp.qq.com            465 (SSL)
  163 邮箱     smtp.163.com           465 (SSL)
  腾讯企业邮   smtp.exmail.qq.com     465 (SSL)
  Gmail        smtp.gmail.com         587 (STARTTLS)
  Outlook      smtp.office365.com     587 (STARTTLS)
"""
import argparse
import mimetypes
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def cfg():
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "465") or 465),
        "user": os.environ.get("SMTP_USER", ""),
        "pwd": os.environ.get("SMTP_PASS", ""),
        "sender": os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER", ""),
    }


def connect(c):
    if not (c["host"] and c["user"] and c["pwd"]):
        print("缺少 SMTP 配置（SMTP_HOST / SMTP_USER / SMTP_PASS）", file=sys.stderr)
        sys.exit(2)
    ctx = ssl.create_default_context()
    if c["port"] == 465:
        s = smtplib.SMTP_SSL(c["host"], c["port"], timeout=30, context=ctx)
    else:
        s = smtplib.SMTP(c["host"], c["port"], timeout=30)
        s.starttls(context=ctx)
    s.login(c["user"], c["pwd"])
    return s


def main():
    ap = argparse.ArgumentParser(description="发邮件（SMTP）")
    ap.add_argument("--to", action="append", default=[], help="收件人（可重复）")
    ap.add_argument("--cc", action="append", default=[], help="抄送（可重复）")
    ap.add_argument("--subject", default="(无主题)")
    ap.add_argument("--body", default="")
    ap.add_argument("--attach", action="append", default=[], help="附件路径（可重复）")
    ap.add_argument("--check", action="store_true", help="只测试登录")
    args = ap.parse_args()

    c = cfg()
    s = connect(c)
    try:
        if args.check:
            print(f"SMTP 登录成功 ✅  {c['host']}:{c['port']}  {c['user']}")
            return
        if not args.to:
            ap.error("请给 --to <收件人>")
        m = EmailMessage()
        m["From"] = c["sender"]
        m["To"] = ", ".join(args.to)
        if args.cc:
            m["Cc"] = ", ".join(args.cc)
        m["Subject"] = args.subject
        m.set_content(args.body or " ")
        for p in args.attach:
            if not os.path.isfile(p):
                print(f"跳过附件（不存在）：{p}", file=sys.stderr)
                continue
            ctype, _ = mimetypes.guess_type(p)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            with open(p, "rb") as fh:
                m.add_attachment(fh.read(), maintype=maintype, subtype=subtype,
                                 filename=os.path.basename(p))
        s.send_message(m, from_addr=c["sender"], to_addrs=args.to + args.cc)
        print(f"已发送 ✅  收件人：{', '.join(args.to)}  主题：{args.subject}")
    finally:
        try:
            s.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
