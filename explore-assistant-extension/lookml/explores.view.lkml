view: explores {
  sql_table_name: ${TABLE} ;;
  
  dimension: id {
    primary_key: yes
    type: string
    sql: ${TABLE}.id ;;
  }
  
  dimension: model_name {
    type: string
    sql: ${TABLE}.model_name ;;
  }
  
  dimension: explore_name {
    type: string
    sql: ${TABLE}.explore_name ;;
  }
  
  dimension: description {
    type: string
    sql: ${TABLE}.description ;;
  }
  
  dimension: label {
    type: string
    sql: ${TABLE}.label ;;
  }
  
  dimension: popularity_score {
    type: number
    sql: ${TABLE}.popularity_score ;;
  }
  
  dimension: fields_json {
    type: string
    sql: ${TABLE}.fields_json ;;
  }
  
  dimension: usage_count {
    type: number
    sql: ${TABLE}.usage_count ;;
  }
  
  dimension_group: last_used {
    type: time
    timeframes: [raw, time, date, week, month, quarter, year]
    sql: ${TABLE}.last_used ;;
  }
  
  dimension_group: created {
    type: time
    timeframes: [raw, time, date, week, month, quarter, year]
    sql: ${TABLE}.created_at ;;
  }
  
  dimension_group: updated {
    type: time
    timeframes: [raw, time, date, week, month, quarter, year]
    sql: ${TABLE}.updated_at ;;
  }
  
  measure: count {
    type: count
    drill_fields: [id, model_name, explore_name, label]
  }
}

explore: explores {
  label: "Explores Metadata"
}