angular.module('core').controller('VPNManagerController', function($scope, $http, $interval, notify) {
    $scope.vpnStatus = {
        tailscale: { connected: false, available_exit_nodes: [] },
        openvpn: { connected: false },
        routing: { mode: 'unknown' }
    };
    $scope.switching = false;
    $scope.monitorActive = false;
    $scope.authUrl = null;
    
    // Load VPN status
    $scope.refreshStatus = function() {
        $http.get('/api/vpn/status').then(function(response) {
            $scope.vpnStatus = response.data;
            $scope.updateMonitorStatus();
        }).catch(function(error) {
            notify.error('Failed to load VPN status');
        });
    };
    
    // Update monitor status
    $scope.updateMonitorStatus = function() {
        $http.get('/api/usb-router/status').then(function(response) {
            $scope.monitorActive = response.data.services['usb-router-vpn-monitor'] === 'active';
        }).catch(function(error) {
            console.log('Could not get monitor status');
        });
    };
    
    // Switch between local and VPN routing
    $scope.switchRouting = function(mode) {
        $scope.switching = true;
        
        $http.post('/api/vpn/routing/switch', { mode: mode }).then(function(response) {
            if (response.data.success) {
                notify.success(response.data.message);
                setTimeout($scope.refreshStatus, 2000);
            } else {
                notify.error('Failed to switch routing: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to switch routing mode');
        }).finally(function() {
            $scope.switching = false;
        });
    };
    
    // Switch Tailscale exit node
    $scope.switchExitNode = function(hostname) {
        $scope.switching = true;
        
        $http.post('/api/vpn/tailscale/switch-exit-node', { hostname: hostname }).then(function(response) {
            if (response.data.success) {
                notify.success(response.data.message);
                setTimeout($scope.refreshStatus, 3000);
            } else {
                notify.error('Failed to switch exit node: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to switch exit node');
        }).finally(function() {
            $scope.switching = false;
        });
    };
    
    // Authenticate Tailscale
    $scope.authenticateTailscale = function() {
        $http.post('/api/vpn/tailscale/authenticate').then(function(response) {
            if (response.data.success) {
                $scope.authUrl = response.data.auth_url;
                $('#authModal').modal('show');
            } else {
                notify.error('Failed to get authentication URL: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to start Tailscale authentication');
        });
    };
    
    // Close authentication modal
    $scope.closeAuthModal = function() {
        $scope.authUrl = null;
        $('#authModal').modal('hide');
    };
    
    // Restart OpenVPN
    $scope.restartOpenVPN = function() {
        $scope.switching = true;
        
        $http.post('/api/vpn/openvpn/restart').then(function(response) {
            if (response.data.success) {
                notify.success(response.data.message);
                setTimeout($scope.refreshStatus, 3000);
            } else {
                notify.error('Failed to restart OpenVPN: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to restart OpenVPN');
        }).finally(function() {
            $scope.switching = false;
        });
    };
    
    // Toggle VPN monitor
    $scope.toggleMonitor = function() {
        $scope.switching = true;
        
        $http.post('/api/vpn/monitor/toggle').then(function(response) {
            if (response.data.success) {
                notify.success(response.data.message);
                $scope.updateMonitorStatus();
            } else {
                notify.error('Failed to toggle monitor: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to toggle VPN monitor');
        }).finally(function() {
            $scope.switching = false;
        });
    };
    
    // Auto-refresh every 30 seconds
    var refreshInterval = $interval($scope.refreshStatus, 30000);
    
    // Cleanup interval on scope destroy
    $scope.$on('$destroy', function() {
        if (refreshInterval) {
            $interval.cancel(refreshInterval);
        }
    });
    
    // Initial load
    $scope.refreshStatus();
});