from crypto_market_intel.sources.coindesk_news import parse_coindesk_rss


def test_parse_coindesk_rss_reads_items():
    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\">
  <channel>
    <item>
      <title>News A</title>
      <link>https://www.coindesk.com/a</link>
      <guid>a-1</guid>
      <pubDate>Thu, 14 May 2026 10:00:00 GMT</pubDate>
      <description>desc a</description>
    </item>
    <item>
      <title>News B</title>
      <link>https://www.coindesk.com/b</link>
      <guid>b-1</guid>
      <pubDate>Thu, 14 May 2026 11:00:00 GMT</pubDate>
      <description>desc b</description>
    </item>
  </channel>
</rss>
"""

    records = parse_coindesk_rss(xml, limit=10)

    assert len(records) == 2
    assert records[0].source_name == "coindesk_news"
    assert records[0].source_record_id == "a-1"
    assert records[1].title == "News B"
