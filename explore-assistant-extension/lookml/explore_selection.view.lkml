view: explore_selection {
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
  
  dimension: explore_id {
    type: string
    sql: ${TABLE}.explore_id ;;
  }
  
  dimension: user_id {
    type: string
    sql: ${TABLE}.user_id ;;
  }
  
  dimension: selection_data {
    type: string
    sql: ${TABLE}.selection_data ;;
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
}

explore: explore_selection {
  label: "Explore Selection"
}