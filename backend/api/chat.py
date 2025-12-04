"""
API routes for AI-powered chat assistance.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict

from backend.models import ChatRequest, ChatResponse, ChatMessage

router = APIRouter()

# In-memory chat history (per session)
_chat_history: List[Dict[str, str]] = []

# Knowledge base for Pi-hole troubleshooting
KNOWLEDGE_BASE = """
# Pi-hole & Unbound Knowledge Base

## Common Issues and Solutions

### DNS Not Resolving

**Symptoms**: Websites not loading, "DNS_PROBE_FINISHED_NXDOMAIN" errors

**Checks**:
1. Verify Pi-hole is running: `docker ps` or `pihole status`
2. Check if port 53 is listening: `netstat -tlnp | grep :53`
3. Test local resolution: `dig @127.0.0.1 google.com`
4. Check firewall: `sudo ufw status` or `iptables -L -n`

**Solutions**:
- Restart Pi-hole: `docker restart pihole` or `pihole restartdns`
- Check logs: `docker logs pihole` or `cat /var/log/pihole.log`
- Verify upstream DNS is reachable

### Unbound Not Working

**Symptoms**: Slow DNS, timeout errors, SERVFAIL responses

**Checks**:
1. Test Unbound directly: `dig @127.0.0.1 -p 5335 google.com`
2. Check Unbound status: `systemctl status unbound`
3. Verify config: `unbound-checkconf`

**Solutions**:
- Restart Unbound: `systemctl restart unbound`
- Check root hints are updated
- Verify DNSSEC trust anchor: `unbound-anchor -a /var/lib/unbound/root.key`

### Clients Not Using Pi-hole

**Causes**:
- Router not configured correctly
- Devices using hardcoded DNS
- DHCPv6 providing different DNS

**Solutions**:
- Verify router DNS settings
- Block port 53 to all except Pi-hole on router
- Disable IPv6 DNS advertisements

## Docker Commands

```bash
# View logs
docker logs -f pihole
docker logs -f unbound

# Execute commands
docker exec pihole pihole -g  # Update gravity
docker exec pihole pihole -t  # Tail query log

# Restart
docker restart pihole
docker-compose down && docker-compose up -d

# Update
docker-compose pull
docker-compose up -d
```

## DNSSEC

**Enable in Pi-hole**: Settings > DNS > Use DNSSEC

**Test DNSSEC**:
```bash
dig +dnssec google.com @127.0.0.1
# Look for "ad" flag in response
```
"""


def build_system_prompt(context: dict = None) -> str:
    """Build the system prompt with embedded knowledge."""
    context_section = ""
    if context:
        context_section = f"""
## User's Configuration

The user has the following setup:
- Deployment: {context.get('deployment', 'unknown')}
- Pi-hole IP: {context.get('pihole_ip', 'unknown')}
- Unbound enabled: {context.get('enable_unbound', 'unknown')}
- IPv6: {context.get('ipv6', False)}
- DHCP: {context.get('dhcp_enabled', False)}

Use this information to provide targeted advice.
"""

    return f"""You are an expert assistant for Pi-hole and Unbound DNS configuration.
Your role is to help users set up, configure, and troubleshoot their Pi-hole and Unbound installation.

## Guidelines

1. **Be specific**: Provide exact commands, file paths, and configuration snippets.
2. **Diagnose first**: Ask clarifying questions if needed before suggesting fixes.
3. **Explain why**: Help users understand the cause of issues, not just fixes.
4. **Safety first**: Warn about potentially destructive operations.
5. **Be concise**: Get to the point, but be thorough when needed.

## Response Format

- Use markdown formatting for readability
- Put commands in code blocks with bash syntax
- Use bullet points for lists of steps
- Highlight important warnings with bold text

{context_section}

## Embedded Knowledge Base

{KNOWLEDGE_BASE}

Remember: You have access to the knowledge base above, but you can also use your general knowledge about Linux, networking, DNS, and Docker to help users.
"""


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message to the AI assistant and get a response."""
    global _chat_history

    if not request.api_key:
        raise HTTPException(
            status_code=400,
            detail="API key required. Enter your Anthropic API key to use the chat feature."
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=request.api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid API key: {str(e)}")

    # Add user message to history
    _chat_history.append({
        "role": "user",
        "content": request.message
    })

    # Keep history manageable
    if len(_chat_history) > 20:
        _chat_history = _chat_history[-20:]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=build_system_prompt(),
            messages=_chat_history
        )

        assistant_message = response.content[0].text

        # Add assistant response to history
        _chat_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return ChatResponse(response=assistant_message)

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_chat_history() -> List[ChatMessage]:
    """Get the chat history."""
    return [ChatMessage(role=m["role"], content=m["content"]) for m in _chat_history]


@router.delete("/history")
async def clear_chat_history():
    """Clear the chat history."""
    global _chat_history
    _chat_history = []
    return {"message": "Chat history cleared"}


@router.get("/quick-prompts")
async def get_quick_prompts():
    """Get quick action prompts for common issues."""
    return {
        "prompts": [
            {
                "label": "DNS not working",
                "message": "My DNS is not resolving. Websites won't load. How do I troubleshoot?"
            },
            {
                "label": "Slow queries",
                "message": "DNS queries are slow. How can I diagnose and fix this?"
            },
            {
                "label": "Ads not blocked",
                "message": "Ads are still showing on some websites. How do I fix this?"
            },
            {
                "label": "Check status",
                "message": "How do I verify my Pi-hole and Unbound are working correctly?"
            },
        ]
    }
