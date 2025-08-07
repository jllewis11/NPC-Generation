"""
Performance monitoring and optimization utilities.
"""
import time
import psutil
import os
import json
from typing import Dict, Any, List
from functools import wraps
import threading
from collections import defaultdict

class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_time = time.time()
        self._lock = threading.Lock()
    
    def time_function(self, func_name: str = None):
        """Decorator to time function execution."""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start
                    self.record_metric("function_time", {
                        "name": name,
                        "duration": duration,
                        "success": True
                    })
                    return result
                except Exception as e:
                    duration = time.time() - start
                    self.record_metric("function_time", {
                        "name": name,
                        "duration": duration,
                        "success": False,
                        "error": str(e)
                    })
                    raise
            return wrapper
        return decorator
    
    def record_metric(self, metric_type: str, data: Dict[str, Any]):
        """Record a performance metric."""
        with self._lock:
            self.metrics[metric_type].append({
                "timestamp": time.time(),
                "data": data
            })
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_mb": psutil.virtual_memory().used / 1024 / 1024,
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "process_count": len(psutil.pids())
        }
    
    def get_function_stats(self) -> Dict[str, Any]:
        """Get aggregated function performance statistics."""
        function_times = self.metrics.get("function_time", [])
        if not function_times:
            return {}
        
        stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "success_count": 0,
            "error_count": 0
        })
        
        for entry in function_times:
            name = entry["data"]["name"]
            duration = entry["data"]["duration"]
            success = entry["data"]["success"]
            
            stats[name]["count"] += 1
            stats[name]["total_time"] += duration
            stats[name]["min_time"] = min(stats[name]["min_time"], duration)
            stats[name]["max_time"] = max(stats[name]["max_time"], duration)
            
            if success:
                stats[name]["success_count"] += 1
            else:
                stats[name]["error_count"] += 1
        
        # Calculate averages
        for name in stats:
            if stats[name]["count"] > 0:
                stats[name]["avg_time"] = stats[name]["total_time"] / stats[name]["count"]
                stats[name]["success_rate"] = stats[name]["success_count"] / stats[name]["count"]
        
        return dict(stats)
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        return {
            "uptime_seconds": time.time() - self.start_time,
            "system_metrics": self.get_system_metrics(),
            "function_stats": self.get_function_stats(),
            "total_metrics_recorded": sum(len(v) for v in self.metrics.values())
        }
    
    def save_report(self, filename: str = "performance_report.json"):
        """Save performance report to file."""
        report = self.generate_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Performance report saved to {filename}")

# Global performance monitor instance
monitor = PerformanceMonitor()

def analyze_bundle_size():
    """Analyze the size of various project components."""
    sizes = {}
    
    # Check Python file sizes
    python_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                size = os.path.getsize(path)
                python_files.append((path, size))
    
    sizes['python_files'] = {
        'total_size_bytes': sum(size for _, size in python_files),
        'file_count': len(python_files),
        'largest_files': sorted(python_files, key=lambda x: x[1], reverse=True)[:5]
    }
    
    # Check dependency sizes
    if os.path.exists('poetry.lock'):
        sizes['poetry_lock_size'] = os.path.getsize('poetry.lock')
    
    # Check data directory
    if os.path.exists('data'):
        data_size = 0
        for root, dirs, files in os.walk('data'):
            for file in files:
                path = os.path.join(root, file)
                data_size += os.path.getsize(path)
        sizes['data_directory_bytes'] = data_size
    
    return sizes

def get_optimization_recommendations() -> List[str]:
    """Generate optimization recommendations based on current state."""
    recommendations = []
    
    # Check if config.py is being used
    try:
        import config
        recommendations.append("✅ Using centralized configuration - Good!")
    except ImportError:
        recommendations.append("❌ Consider implementing centralized configuration")
    
    # Check system resources
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 80:
        recommendations.append(f"⚠️ High memory usage ({memory_percent:.1f}%) - Consider reducing concurrent operations")
    
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent > 80:
        recommendations.append(f"⚠️ High CPU usage ({cpu_percent:.1f}%) - Consider optimizing computation")
    
    # Check file sizes
    bundle_analysis = analyze_bundle_size()
    total_py_size = bundle_analysis['python_files']['total_size_bytes']
    if total_py_size > 100 * 1024:  # 100KB
        recommendations.append(f"💡 Large Python codebase ({total_py_size/1024:.1f}KB) - Consider code splitting")
    
    return recommendations

if __name__ == "__main__":
    # Generate and display performance report
    report = monitor.generate_report()
    print("=== Performance Report ===")
    print(json.dumps(report, indent=2))
    
    print("\n=== Bundle Size Analysis ===")
    bundle_analysis = analyze_bundle_size()
    print(json.dumps(bundle_analysis, indent=2))
    
    print("\n=== Optimization Recommendations ===")
    recommendations = get_optimization_recommendations()
    for rec in recommendations:
        print(rec)
    
    # Save report
    monitor.save_report()