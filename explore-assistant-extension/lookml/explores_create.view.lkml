view: explores_create {
  derived_table: {
    sql:
      CREATE TABLE IF NOT EXISTS ${explores.SQL_TABLE_NAME} (
        id STRING NOT NULL,
        model_name STRING NOT NULL,
        explore_name STRING NOT NULL,
        description STRING,
        label STRING,
        popularity_score FLOAT64,
        fields_json STRING,
        usage_count INT64,
        last_used TIMESTAMP,
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

explore: explores_create {
  label: "Explores Table Create"
}