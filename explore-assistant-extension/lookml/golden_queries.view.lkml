view: golden_queries {
  sql_table_name: '<Insert your gcs bq project here>.explore_assistant.olympic_queries` ;;

  dimension: input {
    type: string
    description: "Input prompt question to be answered by the output"
    sql: ${TABLE}.input ;;
  }
  dimension: output {
    type: string
    description: "Query parameters to build the explore, including the fields, filters and viz config."

    sql: ${TABLE}.output ;;
  }
  dimension: explore_id {
    type: string
    description: "Explore id of the explore to pull examples for in a format of lookml_model:lookml_explore"
    sql: ${TABLE}.explore_id ;;
  }
  dimension: rank {
    type: string
    sql: ${TABLE}.rank ;;
  }
  measure: count {
    type: count
  }
}
