"""
Blocklist API endpoints for the Pi-hole Wizard.
"""

import httpx
import re
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class BlocklistSampleResponse(BaseModel):
    """Response containing sample domains from a blocklist."""
    list_id: str
    domains: List[str]
    total_estimated: int
    is_sample: bool


# Blocklist URLs
BLOCKLIST_URLS = {
    'stevenblack': 'https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts',
    'oisd': 'https://big.oisd.nl/domainswild',
    'hagezi': 'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/pro.txt',
    'firebog-ticked': 'https://v.firebog.net/hosts/lists.php?type=tick',
    'adguard-dns': 'https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt',
    'nocoin': 'https://raw.githubusercontent.com/hoshsadiq/adblock-nocoin-list/master/hosts.txt',
}

# Estimated domain counts
ESTIMATED_COUNTS = {
    'stevenblack': 130000,
    'oisd': 200000,
    'hagezi': 300000,
    'firebog-ticked': 500000,
    'adguard-dns': 50000,
    'nocoin': 10000,
}

# Sample domains for fallback (when network isn't available)
SAMPLE_DOMAINS = {
    'stevenblack': [
        'ads.google.com', 'pagead2.googlesyndication.com', 'ad.doubleclick.net',
        'tracking.example.com', 'analytics.facebook.com', 'pixel.facebook.com',
        'ads.twitter.com', 'advertising.amazon.com', 'adserver.example.net',
        'track.example.org', 'metrics.example.com', 'telemetry.microsoft.com',
        'googleadservices.com', 'googlesyndication.com', 'doubleclick.net',
        'adnxs.com', 'facebook.net', 'advertising.com'
    ],
    'oisd': [
        'ad.example.com', 'tracker.example.com', 'analytics.example.com',
        'pixel.tracking.com', 'ads.cdn.example.net', 'marketing.example.org',
        'beacon.example.com', 'stats.example.com', 'click.example.com',
        'data.adsrvr.org', 'track.hubspot.com', 'segment.io'
    ],
    'hagezi': [
        'telemetry.example.com', 'analytics-api.example.com', 'data.collector.net',
        'tracking-pixel.example.org', 'user-metrics.example.com', 'ad-cdn.example.net',
        'app-measurement.com', 'crashlytics.com', 'appsflyer.com'
    ],
    'firebog-ticked': [
        'malware.example.com', 'phishing.example.net', 'suspicious.example.org',
        'known-bad.example.com', 'threat.example.net', 'dangerous.example.org',
        'malwaredomainlist.com', 'malc0de.com', 'ransomwaretracker.abuse.ch'
    ],
    'adguard-dns': [
        'ads.adguard-example.com', 'tracker.adguard-example.net',
        'banner.example.com', 'pop-up.example.net', 'interstitial.example.org',
        'googleads.g.doubleclick.net', 'static.doubleclick.net'
    ],
    'nocoin': [
        'coinhive.com', 'coin-hive.com', 'cryptoloot.pro', 'crypto-miner.example.net',
        'miner.example.com', 'coin-pool.example.org', 'mining-script.example.net',
        'jsecoin.com', 'authedmine.com', 'minero.cc'
    ]
}


def parse_hosts_file(content: str) -> List[str]:
    """Parse a hosts file format and extract domains."""
    domains = []
    for line in content.split('\n'):
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        # Parse hosts file format: "0.0.0.0 domain.com" or "127.0.0.1 domain.com"
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ('0.0.0.0', '127.0.0.1'):
            domain = parts[1].strip()
            if domain and domain != 'localhost' and '.' in domain:
                domains.append(domain)
        elif len(parts) == 1 and '.' in parts[0]:
            # Plain domain format
            domains.append(parts[0])
    return domains


def parse_adblock_filter(content: str) -> List[str]:
    """Parse AdBlock filter format and extract domains."""
    domains = []
    for line in content.split('\n'):
        line = line.strip()
        # Skip comments and headers
        if not line or line.startswith('!') or line.startswith('['):
            continue
        # Extract domain from ||domain^ format
        if line.startswith('||') and '^' in line:
            domain = line[2:line.index('^')]
            if '.' in domain and not domain.startswith('*'):
                domains.append(domain)
    return domains


@router.get("/{list_id}/sample", response_model=BlocklistSampleResponse)
async def get_blocklist_sample(list_id: str, limit: int = 50):
    """
    Get a sample of domains from a blocklist.

    For performance, this fetches only a portion of the list
    and returns up to 'limit' domains.
    """
    if list_id not in BLOCKLIST_URLS:
        raise HTTPException(status_code=404, detail=f"Unknown blocklist: {list_id}")

    url = BLOCKLIST_URLS[list_id]
    estimated = ESTIMATED_COUNTS.get(list_id, 1000)

    try:
        # Fetch with timeout and partial content
        async with httpx.AsyncClient() as client:
            # Only fetch first 100KB to get a sample
            response = await client.get(
                url,
                timeout=10.0,
                headers={'Range': 'bytes=0-102400'}  # First 100KB
            )

            if response.status_code not in (200, 206):
                # Return sample domains as fallback
                return BlocklistSampleResponse(
                    list_id=list_id,
                    domains=SAMPLE_DOMAINS.get(list_id, [])[:limit],
                    total_estimated=estimated,
                    is_sample=True
                )

            content = response.text

            # Parse based on list type
            if list_id in ('stevenblack', 'nocoin'):
                domains = parse_hosts_file(content)
            elif list_id == 'adguard-dns':
                domains = parse_adblock_filter(content)
            elif list_id == 'firebog-ticked':
                # This returns a list of URLs, not domains
                # Return sample domains instead
                return BlocklistSampleResponse(
                    list_id=list_id,
                    domains=SAMPLE_DOMAINS.get(list_id, [])[:limit],
                    total_estimated=estimated,
                    is_sample=True
                )
            else:
                # Generic domain list (one per line)
                domains = [
                    d.strip() for d in content.split('\n')
                    if d.strip() and not d.strip().startswith('#') and '.' in d
                ]

            # Remove duplicates and limit
            domains = list(dict.fromkeys(domains))[:limit]

            return BlocklistSampleResponse(
                list_id=list_id,
                domains=domains,
                total_estimated=estimated,
                is_sample=True
            )

    except Exception as e:
        # Return sample domains as fallback
        return BlocklistSampleResponse(
            list_id=list_id,
            domains=SAMPLE_DOMAINS.get(list_id, [])[:limit],
            total_estimated=estimated,
            is_sample=True
        )
