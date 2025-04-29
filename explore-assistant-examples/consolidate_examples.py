import os
import json
from pathlib import Path
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig

# Initialize Vertex AI
def init_vertex_ai(project_id, location):
    import vertexai
    vertexai.init(project=project_id, location=location)

# Use LLM to deduplicate and consolidate content
def consolidate_with_llm(contents):
    prompt = f"""
    You are a specialized assistant for consolidating and deduplicating context documents. 
    The input contains overlapping and inconsistent data from multiple files. 
    Your task is to merge the content into a single, coherent document by:
    - Removing duplicates.
    - Resolving inconsistencies.
    - Ensuring the final output is concise and well-structured.
    Here is the input data:
    {contents}
    """
    model = GenerativeModel("gemini-2.0-flash-lite-001")
    response = model.generate_content(
        contents=prompt,
        generation_config=GenerationConfig(
            temperature=0.3,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2000,
            candidate_count=1
        )
    )
    return response.text.strip()

# Consolidate files in a subdirectory
def consolidate_subdirectory(subdir_path, output_dir):
    table_explore_files = {}
    for file in os.listdir(subdir_path):
        if ":" in file:
            table_explore = file.split(":")[1].split(".")[0]
            table_explore_files.setdefault(table_explore, []).append(os.path.join(subdir_path, file))

    for table_explore, files in table_explore_files.items():
        combined_content = []
        for file in files:
            with open(file, "r") as f:
                combined_content.append(f.read())

        # Use LLM to deduplicate and consolidate
        consolidated_content = consolidate_with_llm("\n".join(combined_content))

        # Write consolidated content to the output directory
        output_file = os.path.join(output_dir, f"{table_explore}.txt")
        with open(output_file, "w") as f:
            f.write(consolidated_content)

# Consolidate input files in a subdirectory
def consolidate_inputs_with_llm(contents):
    prompt = f"""
    You are a specialized assistant for consolidating and deduplicating JSON input-output pairs. 
    The input contains overlapping and inconsistent data from multiple files. 
    Your task is to merge the content into a single, coherent JSON array by:
    - Removing duplicates.
    - Resolving inconsistencies.
    - Ensuring the final output is concise and well-structured.
    Here is the input data:
    {contents}
    """
    model = GenerativeModel("gemini-2.0-flash-lite-001")
    response = model.generate_content(
        contents=prompt,
        generation_config=GenerationConfig(
            temperature=0.3,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2000,
            candidate_count=1
        )
    )
    return response.text.strip()

def consolidate_inputs_subdirectory(subdir_path, output_dir):
    input_files = {}
    for file in os.listdir(subdir_path):
        if file.endswith(".inputs.txt"):
            table_explore = file.split(":")[1].split(".")[0]
            input_files.setdefault(table_explore, []).append(os.path.join(subdir_path, file))

    for table_explore, files in input_files.items():
        combined_content = []
        for file in files:
            with open(file, "r") as f:
                combined_content.extend(json.load(f))

        # Use LLM to deduplicate and consolidate
        consolidated_content = consolidate_inputs_with_llm(json.dumps(combined_content))

        # Write consolidated content to the output directory
        output_file = os.path.join(output_dir, f"{table_explore}.inputs.txt")
        with open(output_file, "w") as f:
            f.write(consolidated_content)

# Consolidate input files across subdirectories based on table:explore name
def consolidate_inputs_across_subdirectories(input_dir, output_dir):
    input_files_by_table_explore = {}

    # Group input files by table:explore name
    for subdir in os.listdir(input_dir):
        subdir_path = os.path.join(input_dir, subdir)
        if os.path.isdir(subdir_path):
            for file in os.listdir(subdir_path):
                if file.endswith(".inputs.txt"):
                    table_explore = file.split(":")[1].split(".")[0]
                    input_files_by_table_explore.setdefault(table_explore, []).append(os.path.join(subdir_path, file))

    # Consolidate files for each table:explore
    for table_explore, files in input_files_by_table_explore.items():
        combined_content = []
        for file in files:
            with open(file, "r") as f:
                combined_content.extend(json.load(f))

        # Use LLM to deduplicate and consolidate
        consolidated_content = consolidate_inputs_with_llm(json.dumps(combined_content))

        # Write consolidated content to the output directory
        output_file = os.path.join(output_dir, f"{table_explore}.inputs.txt")
        with open(output_file, "w") as f:
            f.write(consolidated_content)

# Main function
def main():
    project_id = "oss-development-323115"  # Replace with your GCP project ID
    location = "us-central1"  # Replace with your GCP location
    init_vertex_ai(project_id, location)

    input_dir = "/home/colin/looker-explore-assistant/explore-assistant-examples/generated_examples"
    output_dir = "/home/colin/looker-explore-assistant/explore-assistant-examples/generated_examples_combined"
    os.makedirs(output_dir, exist_ok=True)

    for subdir in os.listdir(input_dir):
        subdir_path = os.path.join(input_dir, subdir)
        if os.path.isdir(subdir_path):
            # Consolidate regular files
            consolidate_subdirectory(subdir_path, output_dir)
    
    # Consolidate input files across subdirectories
    consolidate_inputs_across_subdirectories(input_dir, output_dir)

if __name__ == "__main__":
    main()
