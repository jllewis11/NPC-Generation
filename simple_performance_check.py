"""
Simple performance analysis without external dependencies.
"""
import os
import time
import json
from typing import Dict, Any, List

def analyze_codebase_metrics() -> Dict[str, Any]:
    """Analyze basic codebase metrics."""
    metrics = {
        "python_files": 0,
        "total_lines": 0,
        "total_size_bytes": 0,
        "largest_files": [],
        "file_details": []
    }
    
    # Analyze Python files
    for root, dirs, files in os.walk('.'):
        # Skip hidden directories and common build/cache dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    size = os.path.getsize(filepath)
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = len(f.readlines())
                    
                    metrics["python_files"] += 1
                    metrics["total_lines"] += lines
                    metrics["total_size_bytes"] += size
                    
                    file_info = {
                        "path": filepath,
                        "size_bytes": size,
                        "lines": lines
                    }
                    metrics["file_details"].append(file_info)
                    
                except (OSError, UnicodeDecodeError) as e:
                    print(f"Error analyzing {filepath}: {e}")
    
    # Sort and get largest files
    metrics["file_details"].sort(key=lambda x: x["size_bytes"], reverse=True)
    metrics["largest_files"] = metrics["file_details"][:5]
    
    return metrics

def analyze_dependencies() -> Dict[str, Any]:
    """Analyze project dependencies."""
    deps = {
        "requirements_file_exists": False,
        "poetry_file_exists": False,
        "requirements_count": 0,
        "poetry_lock_size": 0
    }
    
    # Check requirements.txt
    if os.path.exists('requirements.txt'):
        deps["requirements_file_exists"] = True
        with open('requirements.txt', 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            deps["requirements_count"] = len(lines)
            deps["requirements_list"] = lines
    
    # Check pyproject.toml
    if os.path.exists('pyproject.toml'):
        deps["poetry_file_exists"] = True
    
    # Check poetry.lock size
    if os.path.exists('poetry.lock'):
        deps["poetry_lock_size"] = os.path.getsize('poetry.lock')
    
    return deps

def check_optimization_patterns() -> Dict[str, bool]:
    """Check if optimization patterns are implemented."""
    patterns = {
        "has_config_module": False,
        "uses_async": False,
        "has_caching": False,
        "uses_typing": False,
        "has_error_handling": False
    }
    
    # Check if config.py exists
    patterns["has_config_module"] = os.path.exists('config.py')
    
    # Check for async/await patterns in code
    async_count = 0
    cache_count = 0
    typing_count = 0
    error_handling_count = 0
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        if 'async ' in content or 'await ' in content:
                            async_count += 1
                        
                        if 'lru_cache' in content or '@cache' in content or 'functools.cache' in content:
                            cache_count += 1
                        
                        if 'from typing import' in content or 'typing.' in content:
                            typing_count += 1
                        
                        if 'try:' in content and 'except' in content:
                            error_handling_count += 1
                            
                except (OSError, UnicodeDecodeError):
                    pass
    
    patterns["uses_async"] = async_count > 0
    patterns["has_caching"] = cache_count > 0
    patterns["uses_typing"] = typing_count > 0
    patterns["has_error_handling"] = error_handling_count > 0
    
    patterns["async_files_count"] = async_count
    patterns["cache_files_count"] = cache_count
    patterns["typing_files_count"] = typing_count
    patterns["error_handling_files_count"] = error_handling_count
    
    return patterns

def get_performance_recommendations() -> List[str]:
    """Generate performance recommendations."""
    recommendations = []
    
    # Analyze metrics
    codebase = analyze_codebase_metrics()
    deps = analyze_dependencies()
    patterns = check_optimization_patterns()
    
    # File size recommendations
    avg_file_size = codebase["total_size_bytes"] / max(codebase["python_files"], 1)
    if avg_file_size > 5000:  # 5KB average
        recommendations.append(f"📦 Large average file size ({avg_file_size:.0f} bytes) - Consider breaking down large modules")
    
    # Line count recommendations
    avg_lines = codebase["total_lines"] / max(codebase["python_files"], 1)
    if avg_lines > 100:
        recommendations.append(f"📄 High average lines per file ({avg_lines:.0f}) - Consider modularization")
    
    # Check for very large files
    for file_info in codebase["largest_files"][:3]:
        if file_info["size_bytes"] > 10000:  # 10KB
            recommendations.append(f"🔍 Large file detected: {file_info['path']} ({file_info['size_bytes']} bytes)")
    
    # Dependencies
    if deps["poetry_lock_size"] > 500 * 1024:  # 500KB
        recommendations.append(f"📚 Large poetry.lock file ({deps['poetry_lock_size']//1024}KB) - Consider dependency cleanup")
    
    if deps["requirements_count"] > 15:
        recommendations.append(f"🔗 Many dependencies ({deps['requirements_count']}) - Review if all are necessary")
    
    # Optimization patterns
    if not patterns["has_config_module"]:
        recommendations.append("⚙️ No config.py found - Consider centralized configuration")
    else:
        recommendations.append("✅ Config module found - Good for centralized configuration!")
    
    if patterns["uses_async"]:
        recommendations.append(f"⚡ Async patterns found in {patterns['async_files_count']} files - Great for performance!")
    else:
        recommendations.append("🐌 No async patterns found - Consider async for I/O operations")
    
    if patterns["has_caching"]:
        recommendations.append(f"💾 Caching found in {patterns['cache_files_count']} files - Excellent for performance!")
    else:
        recommendations.append("💭 No caching patterns found - Consider @lru_cache for expensive operations")
    
    if patterns["uses_typing"]:
        recommendations.append(f"🎯 Type hints found in {patterns['typing_files_count']} files - Good for maintainability!")
    
    if patterns["has_error_handling"]:
        recommendations.append(f"🛡️ Error handling found in {patterns['error_handling_files_count']} files - Good for robustness!")
    
    return recommendations

def generate_performance_report() -> Dict[str, Any]:
    """Generate a comprehensive performance report."""
    return {
        "timestamp": time.time(),
        "codebase_metrics": analyze_codebase_metrics(),
        "dependency_analysis": analyze_dependencies(),
        "optimization_patterns": check_optimization_patterns(),
        "recommendations": get_performance_recommendations()
    }

def main():
    """Main function to run performance analysis."""
    print("🔍 Analyzing codebase performance...")
    print("=" * 50)
    
    report = generate_performance_report()
    
    # Display summary
    codebase = report["codebase_metrics"]
    print(f"📊 Codebase Summary:")
    print(f"   • Python files: {codebase['python_files']}")
    print(f"   • Total lines: {codebase['total_lines']:,}")
    print(f"   • Total size: {codebase['total_size_bytes']/1024:.1f} KB")
    print(f"   • Average file size: {codebase['total_size_bytes']/max(codebase['python_files'], 1):.0f} bytes")
    
    # Display dependencies
    deps = report["dependency_analysis"]
    print(f"\n📚 Dependencies:")
    if deps["requirements_file_exists"]:
        print(f"   • Requirements: {deps['requirements_count']} packages")
    if deps["poetry_lock_size"] > 0:
        print(f"   • Poetry lock: {deps['poetry_lock_size']/1024:.1f} KB")
    
    # Display optimization patterns
    patterns = report["optimization_patterns"]
    print(f"\n⚡ Optimization Patterns:")
    print(f"   • Async usage: {'✅' if patterns['uses_async'] else '❌'}")
    print(f"   • Caching: {'✅' if patterns['has_caching'] else '❌'}")
    print(f"   • Type hints: {'✅' if patterns['uses_typing'] else '❌'}")
    print(f"   • Error handling: {'✅' if patterns['has_error_handling'] else '❌'}")
    print(f"   • Config module: {'✅' if patterns['has_config_module'] else '❌'}")
    
    # Display recommendations
    print(f"\n💡 Recommendations:")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"   {i}. {rec}")
    
    # Save detailed report
    with open('performance_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: performance_analysis.json")

if __name__ == "__main__":
    main()