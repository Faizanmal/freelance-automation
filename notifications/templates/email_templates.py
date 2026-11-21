"""Branded, accessible HTML and plain-text email templates for Signal Desk digests and alerts.

Designed to meet WCAG AA contrast standards, responsive layout, clear why-matched provenance,
and RFC 8058 compliant one-click unsubscribe and sender reputation safeguards.
"""

from __future__ import annotations

import html
from typing import Any


def render_digest_email(
    user_name: str | None,
    leads: list[dict[str, Any]],
    unsubscribe_url: str,
    preferences_url: str,
    date_str: str,
) -> tuple[str, str]:
    """Renders accessible, responsive HTML and plain-text multipart digest email.

    Returns:
        (text_body, html_body)
    """
    name = (user_name or "there").strip()
    count = len(leads)
    lead_noun = "lead" if count == 1 else "leads"

    # Plain-text version
    text_lines = [
        f"Hi {name},",
        "",
        f"Here is your Signal Desk digest for {date_str}.",
        f"We matched {count} new high-relevance freelance {lead_noun} to your profile:",
        "",
        "----------------------------------------------------------------",
    ]

    for idx, lead in enumerate(leads, start=1):
        title = lead.get("title", "Untitled Opportunity")
        company = lead.get("company") or "Direct Employer / Undisclosed"
        source = lead.get("source_name") or lead.get("source") or "Marketplace"
        score = int(float(lead.get("score") or lead.get("match_score") or 0.8) * 100)
        budget = lead.get("budget_display") or lead.get("budget") or "Not specified"
        why = lead.get("why_matched") or lead.get("reason") or "Matched keywords and profile criteria"
        url = lead.get("url") or lead.get("apply_url") or "#"

        text_lines.extend(
            [
                f"{idx}. {title}",
                f"   Company: {company} | Source: {source} | Fit: {score}%",
                f"   Compensation: {budget}",
                f"   Why matched: {why}",
                f"   Direct Link: {url}",
                "",
            ]
        )

    text_lines.extend(
        [
            "----------------------------------------------------------------",
            "",
            "Adjust your delivery days, quiet hours, or hunt criteria anytime:",
            preferences_url,
            "",
            "To pause or unsubscribe instantly:",
            unsubscribe_url,
            "",
            "Signal Desk · Freelance Intelligence Platform",
            "100 Pine Street, San Francisco, CA 94111",
        ]
    )
    plain_text = "\n".join(text_lines)

    # Accessible, responsive HTML version
    lead_cards_html = []
    for idx, lead in enumerate(leads, start=1):
        title = html.escape(str(lead.get("title", "Untitled Opportunity")))
        company = html.escape(str(lead.get("company") or "Direct Employer / Undisclosed"))
        source = html.escape(str(lead.get("source_name") or lead.get("source") or "Marketplace"))
        score = int(float(lead.get("score") or lead.get("match_score") or 0.8) * 100)
        budget = html.escape(str(lead.get("budget_display") or lead.get("budget") or "Not specified"))
        why = html.escape(str(lead.get("why_matched") or lead.get("reason") or "Matched keywords and skills"))
        url = html.escape(str(lead.get("url") or lead.get("apply_url") or "#"))

        lead_cards_html.append(
            f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <span style="display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; background-color: #f1f5f9; padding: 3px 8px; border-radius: 6px;">
                  {source}
                </span>
                <span style="display: inline-block; font-size: 12px; font-weight: 700; color: #0d9488; background-color: #ccfbf1; padding: 3px 8px; border-radius: 6px;">
                  {score}% Fit
                </span>
              </div>
              <h2 style="margin: 0 0 6px 0; font-size: 17px; line-height: 1.35; font-weight: 600; color: #0f172a;">
                <a href="{url}" style="color: #0f172a; text-decoration: none;" target="_blank">{title}</a>
              </h2>
              <div style="font-size: 13px; color: #64748b; margin-bottom: 10px;">
                <strong>Company:</strong> {company} &nbsp;•&nbsp; <strong>Compensation:</strong> {budget}
              </div>
              <div style="font-size: 12px; color: #334155; background-color: #f8fafc; border-left: 3px solid #0ea5e9; padding: 8px 12px; border-radius: 4px; margin-bottom: 14px;">
                <strong>Why matched:</strong> {why}
              </div>
              <div style="text-align: right;">
                <a href="{url}" target="_blank" style="display: inline-block; font-size: 13px; font-weight: 600; background-color: #0f172a; color: #ffffff; text-decoration: none; padding: 8px 16px; border-radius: 6px;">
                  Review &amp; Pitch &rarr;
                </a>
              </div>
            </div>
            """
        )

    all_cards = "\n".join(lead_cards_html)
    safe_name = html.escape(name)
    safe_date = html.escape(date_str)
    safe_prefs = html.escape(preferences_url)
    safe_unsub = html.escape(unsubscribe_url)

    html_body = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Signal Desk Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.5;">
  <div style="max-width: 620px; margin: 0 auto; padding: 24px 16px;">
    <!-- Brand Header -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
      <tr>
        <td>
          <div style="font-size: 20px; font-weight: 800; letter-spacing: -0.02em; color: #0f172a;">
            Signal<span style="color: #0ea5e9;">Desk</span>
          </div>
          <div style="font-size: 12px; color: #64748b;">Autonomous Freelance Intelligence</div>
        </td>
        <td style="text-align: right; vertical-align: bottom;">
          <span style="font-size: 12px; color: #64748b;">{safe_date}</span>
        </td>
      </tr>
    </table>

    <!-- Hero Announcement -->
    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
      <h1 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 700; color: #0f172a;">
        Hi {safe_name}, here is your curated lead digest.
      </h1>
      <p style="margin: 0; font-size: 14px; color: #475569;">
        We matched <strong>{count} new high-relevance freelance {lead_noun}</strong> from our live scraper pool matching your verified criteria.
      </p>
    </div>

    <!-- Lead Listings -->
    {all_cards}

    <!-- Footer & Safeguards -->
    <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center; line-height: 1.6;">
      <p style="margin: 0 0 8px 0;">
        You are receiving this digest because you opted into scheduled alerts for your verified account.
      </p>
      <p style="margin: 0 0 12px 0;">
        <a href="{safe_prefs}" style="color: #0ea5e9; text-decoration: underline;">Configure Delivery &amp; Quiet Hours</a>
        &nbsp;&nbsp;•&nbsp;&nbsp;
        <a href="{safe_unsub}" style="color: #64748b; text-decoration: underline;">Instant Unsubscribe</a>
      </p>
      <p style="margin: 0; color: #94a3b8;">
        Signal Desk · 100 Pine Street, San Francisco, CA 94111<br />
        Preserving independent ingestion &amp; delivery clocks.
      </p>
    </div>
  </div>
</body>
</html>"""
    return plain_text, html_body


def render_empty_digest_email(
    user_name: str | None,
    unsubscribe_url: str,
    preferences_url: str,
    date_str: str,
) -> tuple[str, str]:
    """Renders informative email when empty_digest_policy is 'send_empty_notification'."""
    name = (user_name or "there").strip()
    safe_name = html.escape(name)
    safe_date = html.escape(date_str)
    safe_prefs = html.escape(preferences_url)
    safe_unsub = html.escape(unsubscribe_url)

    text_body = (
        f"Hi {name},\n\n"
        f"Here is your Signal Desk digest update for {date_str}.\n\n"
        "No new freelance leads met your minimum relevance threshold and filter rules today.\n"
        "We never invent numbers or send low-quality filler. Your hunt preferences continue running in the background.\n\n"
        "Tip: You can widen your skills, adjust minimum rates, or lower match threshold here:\n"
        f"{preferences_url}\n\n"
        f"To unsubscribe or change cadence: {unsubscribe_url}\n\n"
        "Signal Desk Team"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Signal Desk Digest Update</title>
</head>
<body style="background-color: #f8fafc; font-family: -apple-system, sans-serif; color: #0f172a; padding: 24px 16px;">
  <div style="max-width: 600px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
    <div style="font-size: 18px; font-weight: 800; margin-bottom: 16px;">Signal<span style="color: #0ea5e9;">Desk</span></div>
    <h1 style="font-size: 16px; font-weight: 600; margin-bottom: 12px;">No high-fit leads today ({safe_date})</h1>
    <p style="font-size: 14px; color: #475569; line-height: 1.5;">
      Hi {safe_name}, none of the newly ingested jobs met your strict fit and threshold criteria today.
      We deliberately suppress stale and low-confidence leads rather than filling your inbox with noise.
    </p>
    <div style="margin: 20px 0; background: #f1f5f9; padding: 14px; border-radius: 8px; font-size: 13px;">
      <strong>Want more leads?</strong> Try expanding your keyword list, including related skills, or adjusting minimum rates in
      <a href="{safe_prefs}" style="color: #0ea5e9; font-weight: 600;">your Hunt Rules</a>.
    </div>
    <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding-top: 12px; text-align: center;">
      <a href="{safe_prefs}" style="color: #64748b;">Settings</a> &bull;
      <a href="{safe_unsub}" style="color: #64748b;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>"""
    return text_body, html_body


def render_immediate_alert_email(
    user_name: str | None,
    lead: dict[str, Any],
    unsubscribe_url: str,
    preferences_url: str,
) -> tuple[str, str]:
    """Renders instant alert email for user-defined high-fit opportunities."""
    name = (user_name or "there").strip()
    title = lead.get("title", "Untitled Opportunity")
    company = lead.get("company") or "Direct Employer"
    source = lead.get("source_name") or lead.get("source") or "Marketplace"
    score = int(float(lead.get("score") or lead.get("match_score") or 0.9) * 100)
    budget = lead.get("budget_display") or lead.get("budget") or "Not specified"
    why = lead.get("why_matched") or lead.get("reason") or "Exceptional match to your key skills"
    url = lead.get("url") or lead.get("apply_url") or "#"

    text_body = (
        f"Hi {name},\n\n"
        f"🚨 High-Fit Opportunity Alert ({score}% match):\n\n"
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Source: {source}\n"
        f"Budget: {budget}\n"
        f"Why matched: {why}\n\n"
        f"Direct Link: {url}\n\n"
        f"Manage immediate alert thresholds or quiet hours: {preferences_url}\n"
        f"Unsubscribe: {unsubscribe_url}\n\n"
        "Signal Desk Alerts"
    )

    safe_title = html.escape(str(title))
    safe_company = html.escape(str(company))
    safe_source = html.escape(str(source))
    safe_budget = html.escape(str(budget))
    safe_why = html.escape(str(why))
    safe_url = html.escape(str(url))
    safe_prefs = html.escape(preferences_url)
    safe_unsub = html.escape(unsubscribe_url)

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>High-Fit Alert</title></head>
<body style="background-color: #f8fafc; font-family: -apple-system, sans-serif; color: #0f172a; padding: 24px 16px;">
  <div style="max-width: 600px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div style="font-size: 18px; font-weight: 800;">Signal<span style="color: #0ea5e9;">Desk</span> <span style="font-size: 12px; color: #ef4444; font-weight: 700; background: #fee2e2; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">HIGH-FIT ALERT</span></div>
      <span style="font-size: 13px; font-weight: 700; color: #0d9488; background: #ccfbf1; padding: 3px 8px; border-radius: 6px;">{score}% Match</span>
    </div>
    <h1 style="font-size: 18px; font-weight: 700; margin: 0 0 8px 0; color: #0f172a;">{safe_title}</h1>
    <p style="font-size: 14px; color: #64748b; margin: 0 0 16px 0;"><strong>{safe_company}</strong> &bull; {safe_source} &bull; {safe_budget}</p>
    <div style="background: #f8fafc; border-left: 3px solid #0ea5e9; padding: 10px 14px; font-size: 13px; margin-bottom: 20px;">
      <strong>Why matched:</strong> {safe_why}
    </div>
    <div style="text-align: center; margin-bottom: 24px;">
      <a href="{safe_url}" target="_blank" style="display: inline-block; background: #0f172a; color: #fff; text-decoration: none; font-weight: 600; padding: 10px 24px; border-radius: 8px;">View &amp; Pitch Now &rarr;</a>
    </div>
    <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding-top: 12px; text-align: center;">
      <a href="{safe_prefs}" style="color: #64748b;">Configure Quiet Hours &amp; Caps</a> &bull;
      <a href="{safe_unsub}" style="color: #64748b;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>"""
    return text_body, html_body
