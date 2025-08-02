#!/bin/bash
# Switch USB router traffic between local WAN and Tailscale exit node

USB_NETWORK="192.168.64.0/24"
USB_INTERFACE="usb0"
WAN_INTERFACE="${WAN_INTERFACE:-wlan0}"
TAILSCALE_INTERFACE="tailscale0"

get_available_exit_nodes() {
    tailscale status --json | jq -r '.Peer[] | select(.ExitNodeOption == true) | .HostName' 2>/dev/null
}

select_exit_node() {
    local exit_nodes=($(get_available_exit_nodes))
    
    if [ ${#exit_nodes[@]} -eq 0 ]; then
        echo "Error: No exit nodes available in your Tailscale network" >&2
        return 1
    fi
    
    if [ ${#exit_nodes[@]} -eq 1 ]; then
        echo "Found one exit node: ${exit_nodes[0]}" >&2
        echo "${exit_nodes[0]}"
        return 0
    fi
    
    echo "Available exit nodes:" >&2
    local i=1
    for node in "${exit_nodes[@]}"; do
        echo "  $i) $node" >&2
        ((i++))
    done
    
    read -p "Select exit node (1-${#exit_nodes[@]}): " selection
    
    # Handle numeric selection
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#exit_nodes[@]} ]; then
        echo "${exit_nodes[$((selection-1))]}"
        return 0
    fi
    
    # Handle direct node name input
    for node in "${exit_nodes[@]}"; do
        if [ "$node" = "$selection" ]; then
            echo "$node"
            return 0
        fi
    done
    
    echo "Invalid selection" >&2
    return 1
}

enable_tailscale_routing() {
    echo "Enabling Tailscale routing..."
    
    # Check current exit node
    local current_exit=$(tailscale status --json | jq -r '.ExitNodeStatus.ID // empty' 2>/dev/null)
    
    if [ -z "$current_exit" ]; then
        local exit_node=$(select_exit_node)
        if [ $? -ne 0 ] || [ -z "$exit_node" ]; then
            echo "Failed to select exit node"
            return 1
        fi
        
        echo "Configuring Tailscale to use exit node: $exit_node"
        tailscale up --exit-node="$exit_node" --exit-node-allow-lan-access
        sleep 3
    else
        echo "Already using an exit node"
    fi
    
    # Clear all existing rules for USB network
    iptables -t nat -D POSTROUTING -s $USB_NETWORK -j MASQUERADE 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j DROP 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $WAN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    
    # Clear existing Tailscale forward rules
    iptables -D FORWARD -i $USB_INTERFACE -o $TAILSCALE_INTERFACE -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o tun0 -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $TAILSCALE_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i tun0 -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    
    # Tailscale-only routing
    iptables -t nat -A POSTROUTING -o $TAILSCALE_INTERFACE -s $USB_NETWORK -j MASQUERADE
    iptables -t nat -A POSTROUTING -o tun0 -s $USB_NETWORK -j MASQUERADE
    
    iptables -A FORWARD -i $USB_INTERFACE -o $TAILSCALE_INTERFACE -j ACCEPT
    iptables -A FORWARD -i $USB_INTERFACE -o tun0 -j ACCEPT
    iptables -A FORWARD -i $TAILSCALE_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i tun0 -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # BLOCK direct WAN access
    iptables -A FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j DROP
    
    # Save rules
    iptables-save > /etc/iptables/rules.v4
    
    echo "USB traffic now routed ONLY through Tailscale (direct internet blocked)"
    echo ""
    echo "Exit node status:"
    tailscale status | grep -E "(offers exit node|proxy-)" || echo "Exit node configured"
}

disable_tailscale_routing() {
    echo "Disabling Tailscale routing..."
    
    # Clear all existing rules for USB network
    iptables -t nat -D POSTROUTING -s $USB_NETWORK -j MASQUERADE 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j DROP 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $WAN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    
    # Clear Tailscale rules
    iptables -D FORWARD -i $USB_INTERFACE -o $TAILSCALE_INTERFACE -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $USB_INTERFACE -o tun0 -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $TAILSCALE_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i tun0 -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    
    # Enable local WAN routing
    iptables -t nat -A POSTROUTING -o $WAN_INTERFACE -s $USB_NETWORK -j MASQUERADE
    iptables -A FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j ACCEPT
    iptables -A FORWARD -i $WAN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Save rules
    iptables-save > /etc/iptables/rules.v4
    
    echo "USB traffic now routed through local WAN"
    echo "Note: You may want to disable the exit node with: tailscale up --exit-node=''"
}

show_status() {
    echo "=== Tailscale Routing Status ==="
    echo ""
    
    # Check if Tailscale routing is enabled
    if iptables -t nat -L POSTROUTING -n | grep -q "MASQUERADE.*$TAILSCALE_INTERFACE.*$USB_NETWORK"; then
        echo "Routing: USB traffic → Tailscale ONLY (direct internet blocked)"
        
        # Check exit node status
        local exit_info=$(tailscale status --json | jq -r '.ExitNodeStatus // empty' 2>/dev/null)
        if [ -n "$exit_info" ] && [ "$exit_info" != "null" ]; then
            local exit_ip=$(echo "$exit_info" | jq -r '.TailscaleIPs[0] // "Unknown"')
            echo "Exit node: Active (IP: $exit_ip)"
        else
            echo "Exit node: Not configured"
        fi
    else
        echo "Routing: USB traffic → Local WAN"
    fi
    
    echo ""
    echo "Available exit nodes:"
    get_available_exit_nodes | sed 's/^/  /'
}

case "$1" in
    on)
        enable_tailscale_routing
        ;;
    off)
        disable_tailscale_routing
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {on|off|status}"
        echo "  on     - Route USB traffic through Tailscale exit node only"
        echo "  off    - Route USB traffic through local internet"
        echo "  status - Show current routing configuration"
        exit 1
        ;;
esac