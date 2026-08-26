import html
from datetime import datetime, timezone

from watch_hunter.models import Listing, SearchCriteria


class EmailFormatter:
    @staticmethod
    def format_subject(listings_count: int) -> str:
        if listings_count == 1:
            return "🎯 Watch Hunter: 1 New Omega Aqua Terra Match Found"
        return f"🎯 Watch Hunter: {listings_count} New Omega Aqua Terra Matches Found"

    @staticmethod
    def format_text(listings: list[Listing], criteria: SearchCriteria) -> str:
        lines: list[str] = [
            "=" * 60,
            "WATCH HUNTER DAILY DIGEST",
            "=" * 60,
            f"Discovered {len(listings)} new listing(s) matching your criteria.",
            f"References: {', '.join(criteria.references)}",
            f"Target Price: €{criteria.min_price_eur:,.0f} - €{criteria.max_price_eur:,.0f} EUR",
            "Regions: Europe / Switzerland",
            "-" * 60,
            "",
        ]

        for i, item in enumerate(listings, start=1):
            price_display = f"{item.price:,.2f} {item.currency}"
            if item.price_eur and item.currency.upper() != "EUR":
                price_display += f" (~€{item.price_eur:,.2f} EUR)"

            lines.extend(
                [
                    f"[{i}] {item.title}",
                    f"    Reference: {item.matched_reference or 'N/A'}",
                    f"    Price:     {price_display}",
                    f"    Condition: {item.condition} ({item.condition_grade.value})",
                    f"    Seller:    {item.seller}",
                    f"    Source:    {item.source.upper()}",
                    f"    Location:  {item.location or 'Not specified'}",
                    f"    URL:       {item.url}",
                    "",
                ]
            )

        lines.extend(
            [
                "-" * 60,
                f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "=" * 60,
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def format_html(listings: list[Listing], criteria: SearchCriteria) -> str:
        items_html = ""
        for item in listings:
            price_display = f"{item.price:,.2f} {html.escape(item.currency)}"
            if item.price_eur and item.currency.upper() != "EUR":
                eur_str = f"~€{item.price_eur:,.2f} EUR"
                price_display += (
                    f' <span style="font-size: 13px; color: #64748b;">({eur_str})</span>'
                )

            image_tag = ""
            if item.image_url:
                img_src = html.escape(item.image_url)
                image_tag = (
                    '<div style="flex-shrink: 0; width: 120px; height: 120px; '
                    "border-radius: 8px; overflow: hidden; background: #f1f5f9; "
                    'margin-right: 16px;">'
                    f'<img src="{img_src}" alt="Watch" '
                    'style="width: 100%; height: 100%; object-fit: cover;" />'
                    "</div>"
                )

            source_color = {
                "ebay": "#0064d2",
                "reddit": "#ff4500",
                "chrono24": "#a86b32",
            }.get(item.source.lower(), "#475569")

            src_badge = (
                f'<span style="background: {source_color}; color: #ffffff; font-size: 11px; '
                f"font-weight: 700; padding: 3px 8px; border-radius: 4px; "
                f'text-transform: uppercase;">{html.escape(item.source)}</span>'
            )
            ref_badge = (
                '<span style="background: #f1f5f9; color: #334155; font-size: 12px; '
                'font-weight: 600; padding: 3px 8px; border-radius: 4px;">'
                f"Ref: {html.escape(item.matched_reference or 'Omega')}</span>"
            )
            cond_label = item.condition_grade.value.replace("_", " ").title()
            cond_badge = (
                '<span style="background: #ecfdf5; color: #065f46; font-size: 12px; '
                'font-weight: 600; padding: 3px 8px; border-radius: 4px;">'
                f"{html.escape(cond_label)}</span>"
            )

            seller_loc = (
                f"<strong>Seller:</strong> {html.escape(item.seller)} &bull; "
                f"<strong>Location:</strong> {html.escape(item.location or 'Europe/Worldwide')}"
            )
            cond_details = f"<strong>Condition:</strong> {html.escape(item.condition)}"

            item_url = html.escape(item.url)
            item_title = html.escape(item.title)

            btn_style = (
                "display: inline-block; background: #0f172a; color: #ffffff; "
                "font-size: 13px; font-weight: 600; padding: 8px 16px; "
                "border-radius: 6px; text-decoration: none;"
            )

            card_style = (
                "background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; "
                "padding: 20px; margin-bottom: 20px; display: flex; "
                "box-shadow: 0 1px 3px rgba(0,0,0,0.05);"
            )

            price_style = "font-size: 18px; font-weight: 700; color: #0284c7; margin-bottom: 12px;"

            items_html += f"""
            <div style="{card_style}">
                {image_tag}
                <div style="flex-grow: 1;">
                    <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
                        {src_badge}
                        {ref_badge}
                        {cond_badge}
                    </div>
                    <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #0f172a;">
                        <a href="{item_url}" style="color: #0f172a; text-decoration: none;">
                            {item_title}
                        </a>
                    </h3>
                    <div style="{price_style}">
                        {price_display}
                    </div>
                    <div style="font-size: 13px; color: #64748b; margin-bottom: 14px;">
                        <div>{seller_loc}</div>
                        <div>{cond_details}</div>
                    </div>
                    <a href="{item_url}" target="_blank" style="{btn_style}">
                        View Listing &rarr;
                    </a>
                </div>
            </div>
            """

        body_style = (
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
            "background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px 0;"
        )
        banner_style = (
            "background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); "
            "color: #ffffff; border-radius: 12px; padding: 28px 24px; "
            "margin-bottom: 24px; text-align: left;"
        )
        gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Watch Hunter Daily Digest</title>
        </head>
        <body style="{body_style}">
            <div style="max-width: 680px; margin: 0 auto; background: #f8fafc; padding: 0 16px;">
                <div style="{banner_style}">
                    <h1 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 800;">
                        🎯 Watch Hunter Daily Digest
                    </h1>
                    <p style="margin: 0; font-size: 14px; color: #94a3b8;">
                        Found <strong>{len(listings)}</strong> new matching listing(s).
                    </p>
                    <div style="margin-top: 14px; font-size: 12px; color: #cbd5e1;">
                        Targets: 231.10.39.21.02.002 &bull; 231.10.39.21.02.001 |
                        Price: €{criteria.min_price_eur:,.0f} - €{criteria.max_price_eur:,.0f} |
                        Region: Europe &amp; Switzerland
                    </div>
                </div>

                <div>
                    {items_html}
                </div>

                <div style="text-align: center; font-size: 12px; color: #94a3b8; padding: 20px 0;">
                    <p style="margin: 0 0 6px 0;">Automated search on eBay and Reddit.</p>
                    <p style="margin: 0;">Discovered at {gen_time}</p>
                </div>
            </div>
        </body>
        </html>
        """
