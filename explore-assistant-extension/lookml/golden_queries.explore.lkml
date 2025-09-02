explore: golden_queries {
  sql_always_where: golden_queries.rank = 'gold' ;;
  join: explore_assistant_refinement_examples {
    type: left_outer
    relationship: one_to_one
    sql_on: ${explore_id} = ${explore_assistant_refinement_examples.explore_id} ;;
  }
  join: explore_assistant_samples {
    type: left_outer
    relationship: one_to_one
    sql_on: false;;
    # ${explore_id} = ${explore_assistant_samples.explore_id} ;;
  }
}