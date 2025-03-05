import os
import csv
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from evaluator import LLMEvaluator
from report_generator import generate_summary_report, generate_detailed_report
from image_handler import ImageHandler

# Import the workflow to test
from workflow import LookerExploreWorkflow
from utils.model_manager import ModelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_questions_from_csv(csv_path: str) -> List[Dict[str, str]]:
    """
    Load test questions from a CSV file
    
    Args:
        csv_path: Path to the CSV file containing test questions
        
    Returns:
        List of dictionaries with question type and text
    """
    questions = []
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                questions.append({
                    "type": row.get("Type", "Unknown"),
                    "text": row.get("Question", "").strip()
                })
        logger.info(f"Loaded {len(questions)} questions from {csv_path}")
        return questions
    except Exception as e:
        logger.error(f"Error loading questions: {e}")
        return []

def run_single_test(workflow: LookerExploreWorkflow, question: Dict[str, str], 
                   evaluator: LLMEvaluator, 
                   image_handler: ImageHandler = None) -> Dict[str, Any]:
    """
    Run a single test question through the workflow and evaluate the response
    
    Args:
        workflow: LookerExploreWorkflow instance
        question: Dictionary containing question type and text
        evaluator: LLMEvaluator instance for assessing response quality
        image_handler: Optional ImageHandler for processing visualization images
        
    Returns:
        Dictionary with test results
    """
    question_text = question["text"]
    question_type = question["type"]
    question_id = question_text.split('.')[0].strip() if '.' in question_text else "NA"
    
    logger.info(f"Testing question {question_id} ({question_type}): {question_text}")
    
    try:
        # Remove any numeric prefix (e.g., "12. ")
        clean_question = question_text.split('.', 1)[1].strip() if '.' in question_text else question_text
        
        # Execute workflow with PNG visualization request
        start_time = datetime.now()
        response = workflow({"query": clean_question, "request_visualization": True})
        end_time = datetime.now()
        
        # Extract visualization data if available
        visualization_data = response.get("visualization_data")
        
        # Prepare result object
        result = {
            "question_id": question_id,
            "question_type": question_type,
            "question_text": clean_question,
            "response_text": response.get("response", ""),
            "explore_url": response.get("explore_url", ""),
            "has_visualization": visualization_data is not None,
            "execution_time": (end_time - start_time).total_seconds(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Save visualization image if available
        visualization_path = None
        if visualization_data and image_handler:
            visualization_path = image_handler.save_image(
                visualization_data,
                f"q{question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            result["visualization_path"] = visualization_path
        
        # Evaluate response
        evaluation = evaluator.evaluate_response(
            question=clean_question,
            response_text=result["response_text"],
            explore_url=result["explore_url"],
            question_type=question_type,
            visualization_data=visualization_data
        )
        
        # Add evaluation results to result
        result.update(evaluation)
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing question {question_id}: {e}")
        return {
            "question_id": question_id,
            "question_type": question_type,
            "question_text": question_text,
            "error": str(e),
            "status": "failed",
            "timestamp": datetime.now().isoformat()
        }

def run_batch_test(questions: List[Dict[str, str]], 
                  config: Dict[str, Any], 
                  output_dir: str,
                  limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Run a batch of test questions and generate reports
    
    Args:
        questions: List of question dictionaries
        config: Configuration for the test run
        output_dir: Directory to save test results
        limit: Optional limit to the number of questions to process
        
    Returns:
        Dictionary with summary statistics
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create image output directory
    images_dir = os.path.join(output_dir, "visualizations")
    os.makedirs(images_dir, exist_ok=True)
    
    # Initialize components
    model_manager = ModelManager()
    workflow = LookerExploreWorkflow(
        model_manager=model_manager,
        looker_instance_url=config.get("looker_instance_url", "")
    )
    evaluator = LLMEvaluator(model_manager)
    image_handler = ImageHandler(screenshot_dir=images_dir)
    
    # Limit the number of questions if specified
    if limit and limit > 0:
        questions = questions[:limit]
    
    results = []
    start_time = datetime.now()
    
    for i, question in enumerate(questions):
        logger.info(f"Processing question {i+1}/{len(questions)}")
        result = run_single_test(workflow, question, evaluator, image_handler)
        results.append(result)
        
        # Save progress after each question
        with open(os.path.join(output_dir, "results_in_progress.json"), "w") as f:
            json.dump(results, f, indent=2)
    
    end_time = datetime.now()
    
    # Generate summary statistics
    summary = {
        "total_questions": len(results),
        "successful_tests": len([r for r in results if r.get("status") != "failed"]),
        "failed_tests": len([r for r in results if r.get("status") == "failed"]),
        "correct_answers": len([r for r in results if r.get("correctness_score", 0) >= 0.7]),
        "visualization_count": len([r for r in results if r.get("has_visualization", False)]),
        "execution_time": (end_time - start_time).total_seconds(),
        "timestamp": datetime.now().isoformat(),
        "config": config
    }
    
    # Save results to files
    results_file = os.path.join(output_dir, "test_results.json")
    summary_file = os.path.join(output_dir, "summary.json")
    
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
        
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Generate HTML reports
    generate_summary_report(results, os.path.join(output_dir, "summary_report.html"))
    generate_detailed_report(results, os.path.join(output_dir, "detailed_report.html"))
    
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests on Looker Explore Assistant")
    parser.add_argument("--questions", default="../documents/question_set.csv", 
                        help="Path to CSV file with test questions")
    parser.add_argument("--output", default="./test_results", 
                        help="Directory to save test results")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit the number of questions to process")
    parser.add_argument("--looker-url", default="https://looker-dev.company.com",
                        help="URL of the Looker instance")
    parser.add_argument("--skip-visualizations", action="store_true",
                        help="Skip requesting and evaluating visualizations")
    parser.add_argument("--question-id", type=str, default=None,
                        help="Run a single test by question ID")
    parser.add_argument("--question-text", type=str, default=None,
                        help="Run a single test with the specified question text")
    
    args = parser.parse_args()
    
    # Create a timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(args.output, f"test_run_{timestamp}")
    
    config = {
        "looker_instance_url": args.looker_url,
        "skip_visualizations": args.skip_visualizations
    }
    
    # Load questions from CSV
    all_questions = load_questions_from_csv(args.questions)
    
    if not all_questions:
        logger.error("No questions loaded. Exiting.")
        exit(1)
    
    # Filter questions based on command line arguments
    if args.question_id:
        questions = [q for q in all_questions if q["text"].startswith(f"{args.question_id}.")]
        if not questions:
            logger.error(f"No question found with ID: {args.question_id}")
            exit(1)
        logger.info(f"Running single test with ID: {args.question_id}")
    elif args.question_text:
        # Create a single question entry with the provided text
        questions = [{"type": "Custom", "text": args.question_text}]
        logger.info(f"Running single test with custom question: {args.question_text}")
    else:
        questions = all_questions
        if args.limit and args.limit > 0:
            questions = questions[:args.limit]
    
    summary = run_batch_test(
        questions=questions,
        config=config,
        output_dir=output_dir,
        limit=None  # We've already filtered the questions
    )
    
    logger.info(f"Testing complete. Results saved to {output_dir}")
    logger.info(f"Summary: {json.dumps(summary, indent=2)}")
