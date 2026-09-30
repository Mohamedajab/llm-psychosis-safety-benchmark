# Security and sensitive data

Do not commit API keys, provider credentials, raw private conversations, rater identities, blinding
maps, or unrestricted exports. Use environment variables for credentials and keep raw collection
records under ignored `data/raw/` paths.

The benchmark prompts include references to psychological distress, unsafe confrontation,
self-injury risk, and social isolation. Treat generated outputs as potentially distressing. Do not
deploy this repository as a mental-health service or expose its collection endpoints to users.

If a credential appears in Git history, revoke it first. Removing the file is not sufficient.
