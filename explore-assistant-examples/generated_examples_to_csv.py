import os
import glob
import json
import csv

# Directory containing the input files
input_dir = "generated_examples_combined"
output_csv = "combined_examples.csv"
base_url = "https://insightsdev.ossd.co/explore/desks_table:"

# Open the output CSV file
with open(output_csv, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    # Write the header row
    writer.writerow(["original_filename", "input", "output", "link"])

    # Iterate over all .inputs.txt files in the directory
    for filepath in glob.glob(os.path.join(input_dir, "*.inputs.txt")):
        filename = os.path.basename(filepath)
        file_prefix = filename.split(".")[0]  # Extract the file prefix

        # Read the JSON content from the file
        with open(filepath, mode="r", encoding="utf-8") as file:
            data = json.load(file)
            for entry in data:
                input_text = entry.get("input", "")
                output_text = entry.get("output", "")
                link = f"{base_url}{file_prefix}"
                # Write the row to the CSV
                writer.writerow([filename, input_text, output_text, link])

print(f"CSV file '{output_csv}' has been created.")