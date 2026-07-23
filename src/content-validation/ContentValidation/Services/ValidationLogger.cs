namespace ContentValidation.Services;

internal class ValidationLogger {
    private readonly string? _logsDir;
    private readonly string _submissionId;
    private readonly bool _isInitialized;

    internal ValidationLogger(string submissionId) {
        _submissionId = submissionId;

        try {
            var storagePath = Environment.GetEnvironmentVariable("PATH_STORAGE");
            if (string.IsNullOrEmpty(storagePath)) {
                _isInitialized = false;
                return;
            }

            _logsDir = Path.Combine(storagePath, "submissions", _submissionId, "logs");
            Directory.CreateDirectory(_logsDir);
            _isInitialized = true;
        }
        catch { _isInitialized = false; }
    }

    internal void Info(string message) => Log("INFO", message, "validation.log");
    internal void Debug(string message) => Log("DEBUG", message, "validation.log");
    internal void Warn(string message) => Log("WARN", message, "validation.log");

    internal void Error(string message, Exception? ex = null) {
        var fullMessage = ex is not null ? $"{message}\n{ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}" : message;
        Log("ERROR", fullMessage, "errors.log");
        Log("ERROR", message, "validation.log");
    }

    internal void LogLlmCall(string checkId, string promptFileName, string requestText, string response, int attempt, bool isValidJson) {
        if (!_isInitialized || string.IsNullOrEmpty(_logsDir))
            return;

        try {
            var timestamp = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");
            var status = isValidJson ? "SUCCESS" : "JSON_ERROR";

            var entry = new System.Text.StringBuilder();

            entry.AppendLine($"{new string('#', 128)}");
            entry.AppendLine($"[{timestamp}] {checkId} | REQUEST | Attempt {attempt}");
            entry.AppendLine($"Prompt file: {promptFileName}");
            entry.AppendLine($"Text length: {requestText.Length} chars");
            entry.AppendLine($"{requestText}\n");
            entry.AppendLine($"{new string('-', 128)}\n");

            entry.AppendLine($"[{timestamp}] {checkId} | RESPONSE | Attempt {attempt} | {status}");
            entry.AppendLine(response);
            entry.AppendLine($"{new string('#', 128)}\n\n\n\n");

            File.AppendAllText(Path.Combine(_logsDir, "llm_calls.log"), entry.ToString());
        }
        catch { }
    }

    private void Log(string level, string message, string filename) {
        if (!_isInitialized || string.IsNullOrEmpty(_logsDir))
            return;

        try {
            var timestamp = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");
            var logEntry = $"[{timestamp}] {level,-5} | {message}\n";

            var logPath = Path.Combine(_logsDir, filename);
            File.AppendAllText(logPath, logEntry);
        }
        catch { }
    }
}
