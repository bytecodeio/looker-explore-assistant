view: explore_selection_create {
  derived_table: {
    sql:
      CREATE TABLE IF NOT EXISTS ${explore_selection.SQL_TABLE_NAME} (
        id STRING NOT NULL,
        model_name STRING NOT NULL,
        explore_id STRING NOT NULL,
        user_id STRING NOT NULL,
        selection_data STRING,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        PRIMARY KEY(id)
      )
    ;;
    sql_create: {}
  }

  dimension: creation_status {
    type: string
    sql: 'Table Created Successfully' ;;
  }
}

explore: explore_selection_create {
  label: "Explore Selection Create"
}