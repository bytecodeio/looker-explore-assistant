application: explore_assistant {
    label: "Explore Assistant"
    file: "bundle.js"
    entitlements: {
      local_storage: yes
      navigation: yes
      new_window: yes
      new_window_external_urls: ["https://developers.generativeai.google/*"]
      use_form_submit: no
      use_embeds: yes
      use_iframes: yes
      use_clipboard: no
      core_api_methods: ["lookml_model_explore", "run_inline_query", "run_query", "create_query", "update_user_attribute", "create_user_attribute", "all_user_attributes", "me", "user_attribute_user_values", "search_roles", "login_user", "all_connections","test_connection","connections","connection","all_lookml_models","run_url_encoded_query"]
      external_api_urls: ["<Insert your cloud function url here>", "https://www.googleapis.com"]
      oauth2_urls: ["https://accounts.google.com/o/oauth2/v2/auth"]
    }
}
