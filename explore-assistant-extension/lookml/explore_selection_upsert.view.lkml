view: explore_selection_upsert {
  derived_table: {
    sql_create: 
      MERGE INTO ${explore_selection.SQL_TABLE_NAME} AS target
      USING (
        SELECT 
          {% parameter id %} AS id,
          {% parameter model_name %} AS model_name,
          {% parameter explore_id %} AS explore_id,
          {% parameter user_id %} AS user_id,
          {% parameter selection_data %} AS selection_data,
          CAST({% parameter created_at %} AS TIMESTAMP) AS created_at,
          CURRENT_TIMESTAMP() AS updated_at
      ) AS source
      ON target.id = source.id
      WHEN MATCHED THEN
        UPDATE SET 
          target.model_name = source.model_name,
          target.explore_id = source.explore_id,
          target.user_id = source.user_id,
          target.selection_data = source.selection_data,
          target.updated_at = source.updated_at
      WHEN NOT MATCHED THEN
        INSERT (id, model_name, explore_id, user_id, selection_data, created_at, updated_at)
        VALUES (
          source.id, 
          source.model_name, 
          source.explore_id, 
          source.user_id, 
          source.selection_data, 
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

  parameter: explore_id {
    type: string
  }

  parameter: user_id {
    type: string
  }

  parameter: selection_data {
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

explore: explore_selection_upsert {
  label: "Explore Selection Upsert"
}