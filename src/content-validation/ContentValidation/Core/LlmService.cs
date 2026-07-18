using System.Text.Json;
using ContentValidation.Services;


namespace ContentValidation.Core;

internal class LlmService {
    private readonly LlmClient _client;
    private readonly string _promptsFolder;
    private readonly ValidationLogger _logger;

    internal LlmService(LlmClient client, string promptsFolder, ValidationLogger logger) {
        _client        = client;
        _promptsFolder = promptsFolder;
        _logger        = logger;
    }

    internal async Task<string?> AskAsync(string promptFileName, string text, string checkId) {
        try {
            string prompt = LoadPrompt(promptFileName);

            if (string.IsNullOrEmpty(prompt)) {
                _logger.Error($"Файл промпта не найден: {promptFileName}");
                return null;
            }

            int attempt = 0;
            int maxAttempts = 3;

            while (attempt < maxAttempts) {
                attempt++;

                try {
                    string response = await _client.SendRequestAsync(prompt, text);
                    bool isValidJson = IsValidJson(response);

                    _logger.LogLlmCall(checkId, promptFileName, text, response, attempt, isValidJson);

                    if (isValidJson)
                        return response;

                    _logger.Warn($"Проверка {checkId} - Невалидный JSON {attempt}/{maxAttempts}");

                    if (attempt < maxAttempts)
                        await Task.Delay(1000);
                }
                catch (Exception ex) {
                    _logger.Error($"Проверка {checkId} - ошибка ответа LLM {attempt}/{maxAttempts}", ex);

                    if (attempt < maxAttempts)
                        await Task.Delay(1000);
                }
            }

            _logger.Error($"Проверка {checkId} - Все {maxAttempts} попытки завершились неудачно");
            return null;
        }
        catch (Exception ex) {
            _logger.Error($"Проверка {checkId} - Критическая ошибка при ответе.", ex);
            return null;
        }
    }

    private string LoadPrompt(string promptFileName) {
        try {
            string path = Path.Combine(_promptsFolder, promptFileName);

            if (!File.Exists(path))
                return string.Empty;

            return File.ReadAllText(path);
        }
        catch {
            return string.Empty;
        }
    }

    private bool IsValidJson(string json) {
        if (!string.IsNullOrWhiteSpace(json)) {
            try {
                JsonDocument.Parse(json);
                return true;
            }
            catch { }
        }

        return false;
    }
}
