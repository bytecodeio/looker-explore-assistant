view: explore_assistant_samples {
  sql_table_name: `<Insert your gcs bq project here>.explore_assistant.explore_assistant_samples` ;;

  dimension: explore_id {
    type: string
    description: "Explore id of the explore to pull examples for in a format of -\u003e lookml_model:lookml_explore"
    sql: ${TABLE}.explore_id ;;
  }

  dimension: samples {
    type: string
    description: "Samples for Explore Assistant Samples displayed in UI. JSON document with listed samples with category, prompt and color keys."
    sql: ${TABLE}.samples ;;
  }
}
