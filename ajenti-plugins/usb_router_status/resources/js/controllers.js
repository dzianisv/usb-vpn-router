angular.module('core').controller('USBRouterStatusController', function($scope, $http, $interval, notify) {
    $scope.status = {};
    $scope.loading = true;
    
    // Load initial data
    $scope.refresh = function() {
        $scope.loading = true;
        $http.get('/api/usb-router/status').then(function(response) {
            $scope.status = response.data;
            $scope.loading = false;
        }).catch(function(error) {
            notify.error('Failed to load router status');
            $scope.loading = false;
        });
    };
    
    // Helper functions for percentage calculations
    $scope.getMemoryPercent = function() {
        if (!$scope.status.system || !$scope.status.system.memory) return 0;
        return Math.round(($scope.status.system.memory.used / $scope.status.system.memory.total) * 100);
    };
    
    $scope.getDiskPercent = function() {
        if (!$scope.status.system || !$scope.status.system.disk) return 0;
        return Math.round(($scope.status.system.disk.used / $scope.status.system.disk.total) * 100);
    };
    
    // Reset USB interface
    $scope.resetInterface = function() {
        $http.post('/api/usb-router/reset-interface').then(function(response) {
            if (response.data.success) {
                notify.success('USB interface reset successfully');
                $scope.refresh();
            } else {
                notify.error('Failed to reset interface: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to reset interface');
        });
    };
    
    // Restart service
    $scope.restartService = function(service) {
        $http.post('/api/usb-router/restart-service/' + service).then(function(response) {
            if (response.data.success) {
                notify.success('Service ' + service + ' restarted successfully');
                setTimeout($scope.refresh, 2000); // Refresh after 2 seconds
            } else {
                notify.error('Failed to restart service: ' + response.data.error);
            }
        }).catch(function(error) {
            notify.error('Failed to restart service');
        });
    };
    
    // Auto-refresh every 30 seconds
    var refreshInterval = $interval($scope.refresh, 30000);
    
    // Cleanup interval on scope destroy
    $scope.$on('$destroy', function() {
        if (refreshInterval) {
            $interval.cancel(refreshInterval);
        }
    });
    
    // Initial load
    $scope.refresh();
});