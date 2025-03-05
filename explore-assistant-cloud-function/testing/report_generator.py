import os
import json
from datetime import datetime
from typing import List, Dict, Any

def generate_summary_report(results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Generate a summary HTML report for test results
    
    Args:
        results: List of test result dictionaries
        output_path: Path to save the HTML report
    """
    # Calculate summary statistics
    total = len(results)
    successful = len([r for r in results if r.get("status") != "failed"])
    failed = total - successful
    
    # Calculate average scores
    avg_correctness = sum(r.get("correctness_score", 0) for r in results) / total if total > 0 else 0
    avg_filters = sum(r.get("filters_score", 0) for r in results) / total if total > 0 else 0
    avg_dimensions = sum(r.get("dimensions_score", 0) for r in results) / total if total > 0 else 0
    avg_visualization = sum(r.get("visualization_score", 0) for r in results) / total if total > 0 else 0
    avg_overall = sum(r.get("overall_score", 0) for r in results) / total if total > 0 else 0
    
    # Count performance by question type
    question_types = {}
    for r in results:
        q_type = r.get("question_type", "Unknown")
        if q_type not in question_types:
            question_types[q_type] = {
                "count": 0,
                "total_score": 0,
                "successful": 0
            }
        question_types[q_type]["count"] += 1
        question_types[q_type]["total_score"] += r.get("overall_score", 0)
        if r.get("status") != "failed":
            question_types[q_type]["successful"] += 1
    
    # Calculate averages by question type
    for q_type in question_types:
        if question_types[q_type]["count"] > 0:
            question_types[q_type]["avg_score"] = (
                question_types[q_type]["total_score"] / question_types[q_type]["count"]
            )
            question_types[q_type]["success_rate"] = (
                question_types[q_type]["successful"] / question_types[q_type]["count"]
            )
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Looker Explore Assistant Test Summary</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .summary-stats {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px; }}
        .stat-card {{ background-color: #f9f9f9; border-radius: 5px; padding: 15px; flex: 1; min-width: 200px; }}
        .chart-container {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px; }}
        .chart-card {{ background-color: #f9f9f9; border-radius: 5px; padding: 15px; flex: 1; min-width: 400px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .good {{ color: green; }}
        .average {{ color: orange; }}
        .poor {{ color: red; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Looker Explore Assistant Test Summary</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Total questions tested: {total}</p>
        </div>

        <div class="summary-stats">
            <div class="stat-card">
                <h3>Success Rate</h3>
                <p><strong>{successful}/{total}</strong> ({100 * successful / total:.1f}% successful)</p>
            </div>
            <div class="stat-card">
                <h3>Average Scores</h3>
                <p>Correctness: <strong>{avg_correctness:.2f}</strong></p>
                <p>Filters: <strong>{avg_filters:.2f}</strong></p>
                <p>Dimensions: <strong>{avg_dimensions:.2f}</strong></p>
                <p>Visualization: <strong>{avg_visualization:.2f}</strong></p>
                <p>Overall: <strong>{avg_overall:.2f}</strong></p>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-card">
                <h3>Overall Performance</h3>
                <canvas id="performanceChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>Performance by Question Type</h3>
                <canvas id="questionTypeChart"></canvas>
            </div>
        </div>

        <h2>Performance by Question Type</h2>
        <table>
            <tr>
                <th>Question Type</th>
                <th>Count</th>
                <th>Success Rate</th>
                <th>Average Score</th>
            </tr>
"""

    # Add rows for each question type
    for q_type, stats in question_types.items():
        avg_score = stats.get("avg_score", 0)
        success_rate = stats.get("success_rate", 0)
        score_class = "good" if avg_score >= 0.7 else ("average" if avg_score >= 0.5 else "poor")
        
        html += f"""
            <tr>
                <td>{q_type}</td>
                <td>{stats["count"]}</td>
                <td>{stats["successful"]}/{stats["count"]} ({100 * success_rate:.1f}%)</td>
                <td class="{score_class}">{avg_score:.2f}</td>
            </tr>"""

    # Add JavaScript for charts
    html += """
        </table>
    </div>

    <script>
        // Data for overall performance chart
        const performanceData = {
            labels: ['Correctness', 'Filters', 'Dimensions', 'Visualization', 'Overall'],
            datasets: [{
                label: 'Average Score',
                data: [""" + f"{avg_correctness:.2f}, {avg_filters:.2f}, {avg_dimensions:.2f}, {avg_visualization:.2f}, {avg_overall:.2f}" + """],
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        };

        // Data for question type chart
        const questionTypeData = {
            labels: [""" + ", ".join([f"'{q_type}'" for q_type in question_types]) + """],
            datasets: [{
                label: 'Average Score',
                data: [""" + ", ".join([f"{question_types[q_type].get('avg_score', 0):.2f}" for q_type in question_types]) + """],
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }, {
                label: 'Success Rate',
                data: [""" + ", ".join([f"{question_types[q_type].get('success_rate', 0):.2f}" for q_type in question_types]) + """],
                backgroundColor: 'rgba(153, 102, 255, 0.5)',
                borderColor: 'rgba(153, 102, 255, 1)',
                borderWidth: 1
            }]
        };

        // Create charts
        const performanceCtx = document.getElementById('performanceChart').getContext('2d');
        new Chart(performanceCtx, {
            type: 'bar',
            data: performanceData,
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1.0
                    }
                }
            }
        });

        const questionTypeCtx = document.getElementById('questionTypeChart').getContext('2d');
        new Chart(questionTypeCtx, {
            type: 'bar',
            data: questionTypeData,
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1.0
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html)

def generate_detailed_report(results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Generate a detailed HTML report with individual test results
    
    Args:
        results: List of test result dictionaries
        output_path: Path to save the HTML report
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Looker Explore Assistant Detailed Test Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .question-card { border: 1px solid #ddd; border-radius: 5px; margin-bottom: 20px; overflow: hidden; }
        .question-header { background-color: #f5f5f5; padding: 10px 20px; border-bottom: 1px solid #ddd; }
        .question-body { padding: 20px; }
        .scores { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; }
        .score-item { background-color: #f9f9f9; border-radius: 5px; padding: 8px 15px; }
        .good { color: green; }
        .average { color: orange; }
        .poor { color: red; }
        .response-section { background-color: #f9f9f9; border-radius: 5px; padding: 15px; margin-bottom: 15px; }
        .explore-url { word-break: break-all; background-color: #f0f0f0; padding: 5px; border-radius: 3px; }
        .feedback-section { border-top: 1px solid #eee; padding-top: 15px; margin-top: 15px; }
        .visualization-img { max-width: 100%; border: 1px solid #ddd; margin-top: 15px; }
        summary { cursor: pointer; font-weight: bold; }
        details { margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Looker Explore Assistant Detailed Test Results</h1>
            <p>Generated on: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </div>
"""

    # Sort results by question_id for better organization
    sorted_results = sorted(results, key=lambda x: x.get('question_id', '0'))

    # Add each question result as a card
    for result in sorted_results:
        q_id = result.get('question_id', 'Unknown')
        q_type = result.get('question_type', 'Unknown')
        question = result.get('question_text', '')
        response = result.get('response_text', '')
        explore_url = result.get('explore_url', '')
        status = result.get('status', 'failed')
        
        # Get scores with default values
        correctness = result.get('correctness_score', 0)
        filters = result.get('filters_score', 0)
        dimensions = result.get('dimensions_score', 0)
        visualization = result.get('visualization_score', 0)
        overall = result.get('overall_score', 0)
        
        # Determine color classes based on scores
        correctness_class = "good" if correctness >= 0.7 else ("average" if correctness >= 0.5 else "poor")
        filters_class = "good" if filters >= 0.7 else ("average" if filters >= 0.5 else "poor")
        dimensions_class = "good" if dimensions >= 0.7 else ("average" if dimensions >= 0.5 else "poor")
        visualization_class = "good" if visualization >= 0.7 else ("average" if visualization >= 0.5 else "poor")
        overall_class = "good" if overall >= 0.7 else ("average" if overall >= 0.5 else "poor")
        
        # Get feedback
        correctness_feedback = result.get('correctness_feedback', '')
        filters_feedback = result.get('filters_feedback', '')
        dimensions_feedback = result.get('dimensions_feedback', '')
        visualization_feedback = result.get('visualization_feedback', '')
        improvement_suggestions = result.get('improvement_suggestions', '')
        
        # Check if there's a visualization
        has_vis = result.get('has_visualization', False)
        vis_path = result.get('visualization_path', '')
        vis_img = f'<img src="{vis_path}" class="visualization-img" alt="Visualization">' if vis_path else ''
        
        # Create the card HTML
        html += f"""
        <div class="question-card">
            <div class="question-header">
                <h2>Question {q_id}: {q_type}</h2>
                <p><strong>Status:</strong> {status}</p>
            </div>
            <div class="question-body">
                <h3>Question</h3>
                <p>{question}</p>
                
                <h3>Response</h3>
                <div class="response-section">
                    <pre>{response}</pre>
                </div>
                
                <h3>Explore URL</h3>
                <div class="explore-url">{explore_url}</div>
                
                <h3>Evaluation Scores</h3>
                <div class="scores">
                    <div class="score-item">
                        <strong>Correctness:</strong> <span class="{correctness_class}">{correctness:.2f}</span>
                    </div>
                    <div class="score-item">
                        <strong>Filters:</strong> <span class="{filters_class}">{filters:.2f}</span>
                    </div>
                    <div class="score-item">
                        <strong>Dimensions:</strong> <span class="{dimensions_class}">{dimensions:.2f}</span>
                    </div>
                    <div class="score-item">
                        <strong>Visualization:</strong> <span class="{visualization_class}">{visualization:.2f}</span>
                    </div>
                    <div class="score-item">
                        <strong>Overall:</strong> <span class="{overall_class}">{overall:.2f}</span>
                    </div>
                </div>
                
                <div class="feedback-section">
                    <details>
                        <summary>Correctness Feedback</summary>
                        <p>{correctness_feedback}</p>
                    </details>
                    <details>
                        <summary>Filters Feedback</summary>
                        <p>{filters_feedback}</p>
                    </details>
                    <details>
                        <summary>Dimensions Feedback</summary>
                        <p>{dimensions_feedback}</p>
                    </details>
                    <details>
                        <summary>Visualization Feedback</summary>
                        <p>{visualization_feedback}</p>
                    </details>
                    <details>
                        <summary>Improvement Suggestions</summary>
                        <p>{improvement_suggestions}</p>
                    </details>
                </div>
                
                {vis_img if has_vis else '<p>No visualization available</p>'}
            </div>
        </div>
        """
    
    # Close HTML document
    html += """
    </div>
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html)