view: explores_upsert {
  derived_table: {
    sql_create: 
      MERGE INTO ${explores.SQL_TABLE_NAME} AS target
      USING (
        SELECT 
          {% parameter id %} AS id,
          {% parameter model_name %} AS model_name,
          {% parameter explore_name %} AS explore_name,
          {% parameter description %} AS description,
          {% parameter label %} AS label,
          CAST({% parameter popularity_score %} AS FLOAT64) AS popularity_score,
          {% parameter fields_json %} AS fields_json,
          CAST({% parameter usage_count %} AS INT64) AS usage_count,
          CAST({% parameter last_used %} AS TIMESTAMP) AS last_used,
          CAST({% parameter created_at %} AS TIMESTAMP) AS created_at,
          CURRENT_TIMESTAMP() AS updated_at
      ) AS source
      ON target.id = source.id
      WHEN MATCHED THEN
        UPDATE SET 
          target.model_name = source.model_name,
          target.explore_name = source.explore_name,
          target.description = source.description,
          target.label = source.label,
          target.popularity_score = source.popularity_score,
          target.fields_json = source.fields_json,
          target.usage_count = source.usage_count,
          target.last_used = source.last_used,
          target.updated_at = source.updated_at
      WHEN NOT MATCHED THEN
        INSERT (id, model_name, explore_name, description, label, popularity_score, fields_json, usage_count, last_used, created_at, updated_at)
        VALUES (
          source.id, 
          source.model_name, 
          source.explore_name, 
          source.description,
          source.label,
          source.popularity_score,
          source.fields_json,
          source.usage_count,
          source.last_used,
          source.created_at, 
          source.updated_at
        )
    ;;
  }

  parameter: id {
    type: string
  }

  parameter: model_name {
    type: string
  }

  parameter: explore_name {
    type: string
  }

  parameter: description {
    type: string
  }

  parameter: label {
    type: string
  }

  parameter: popularity_score {
    type: string
  }
  
  parameter: fields_json {
    type: string
  }
  
  parameter: usage_count {
    type: string
  }
  
  parameter: last_used {
    type: string
  }

  parameter: created_at {
    type: string
  }

  dimension: status {
    type: string
    sql: 'Upsert Successful' ;;
  }
}

explore: explores_upsert {
  label: "Explores Upsert"
}