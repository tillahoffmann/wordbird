use zed_extension_api as zed;

/// The Python LSP script is embedded at compile time from the backend source.
const LSP_SCRIPT: &str = include_str!("../../backend/src/wordbird/lsp.py");

struct WordbirdExtension;

impl zed::Extension for WordbirdExtension {
    fn new() -> Self {
        WordbirdExtension
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<zed::Command, String> {
        let python = worktree
            .which("python3")
            .or_else(|| worktree.which("python"))
            .ok_or_else(|| "python3 not found on PATH".to_string())?;

        Ok(zed::Command {
            command: python,
            args: vec!["-c".to_string(), LSP_SCRIPT.to_string()],
            env: Default::default(),
        })
    }
}

zed::register_extension!(WordbirdExtension);
