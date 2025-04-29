##This script will upload new examples from generated_examples_combined/*.inputs.txt to a selected BigQuery dataset

source .env
TABLE_ID="explore_assistant_examples"             ##The ID of the BigQuery table where the data will be inserted. Set to explore_assistant_examples.

# Loop through each *.inputs.txt file and upload it separately
for file in ./generated_examples_combined/*.inputs.txt; do
    echo "Uploading $file to BigQuery..."
    python load_examples.py \
    --project_id $PROJECT_ID \
    --dataset_id $DATASET_ID \
    --explore_id $(basename "$file" .inputs.txt) \
    --table_id $TABLE_ID \
    --json_file "$file" \
    --concat
done
