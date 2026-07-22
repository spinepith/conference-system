using System.Text.Json;
using ContentValidation.Core;


namespace ContentValidation.Models;

internal abstract class BaseChecker {
    private static LlmService? _llmService;

    internal static void Initialize(LlmService llmService) {
        _llmService = llmService;
    }

    protected static async Task<CheckResult> ExecuteCheckAsync(string checkId, string title, string promptFileName, string text) {
        var result = new CheckResult {
            CheckId          = checkId,
            Title            = title,
            Status           = "error",
            RiskLevel        = "high",
            Score            = double.NaN,
            Summary          = "LlmService не инициализирован. Вызовите BaseChecker.Initialize() перед использованием.",
            Warnings         = [],
            Errors           = [],
            FlaggedFragments = [],
            AuthorComment    = "Автоматическая проверка временно недоступна.",
            EditorComment    = "Проверка завершилась с ошибкой. Требуется ручная проверка.",
            RawModelResponse = null
        };

        if (_llmService is null)
            return result;

        try {
            string? response = await _llmService.AskAsync(promptFileName, text, checkId);

            if (string.IsNullOrEmpty(response)) {
                result.Summary = "Не удалось получить ответ от модели после нескольких попыток.";
                return result;
            }

            var llmResult = ParseWithFallback(response, checkId);
            if (llmResult is not null)
                result = llmResult;

            result.RawModelResponse = new CheckResult.RawModelResponseData {
                Model     = Environment.GetEnvironmentVariable("LLM_MODEL") ?? "gemini-3.1-flash-lite",
                Timestamp = DateTime.UtcNow.ToString("o"),
                Response  = response
            };
        }
        catch (JsonException ex) {
            result.Status        = "error";
            result.RiskLevel     = "high";
            result.Summary       = $"Ошибка парсинга ответа модели: {ex.Message}";
            result.EditorComment = "Модель вернула невалидный JSON. Требуется ручная проверка.";
            result.AuthorComment = "Автоматическая проверка завершилась с ошибкой.";
        }
        catch (Exception ex) {
            result.Status        = "error";
            result.RiskLevel     = "high";
            result.Summary       = $"Непредвиденная ошибка: {ex.Message}";
            result.EditorComment = "Проверка завершилась с критической ошибкой.";
            result.AuthorComment = "Автоматическая проверка временно недоступна.";
        }

        return result;
    }

    private static CheckResult ParseWithFallback(string rawJson, string checkId) {
        try {
            var result = JsonSerializer.Deserialize<CheckResult>(rawJson);
            if (result is not null)
                return result;
        }
        catch (JsonException ex) {
            try {
                using var doc = JsonDocument.Parse(rawJson);
                var root = doc.RootElement;

                var result = new CheckResult {
                    CheckId          = GetStringProperty(root, "check_id"),
                    Title            = GetStringProperty(root, "title"),
                    Status           = GetStringProperty(root, "status"),
                    RiskLevel        = GetStringProperty(root, "risk_level"),
                    Score            = GetDoubleProperty(root, "score"),
                    Summary          = GetStringProperty(root, "summary"),
                    Warnings         = new List<CheckResult.CheckIssue>(),
                    Errors           = new List<CheckResult.CheckIssue>(),
                    FlaggedFragments = new List<CheckResult.FlaggedFragment>(),
                    AuthorComment    = GetStringProperty(root, "author_comment"),
                    EditorComment    = GetStringProperty(root, "editor_comment")
                };

                if (root.TryGetProperty("warnings", out var warningsElement)) {
                    if (warningsElement.ValueKind is JsonValueKind.Array) {
                        foreach (var item in warningsElement.EnumerateArray()) {
                            if (item.ValueKind is JsonValueKind.String) {
                                result.Warnings.Add(
                                    new CheckResult.CheckIssue {
                                        Code           = "GENERIC_WARNING",
                                        Message        = item.GetString() ?? "",
                                        Location       = null,
                                        Recommendation = null
                                    }
                                );
                            }
                            else if (item.ValueKind is JsonValueKind.Object) {
                                result.Warnings.Add(
                                    new CheckResult.CheckIssue {
                                        Code           = GetStringProperty(item, "code"),
                                        Message        = GetStringProperty(item, "message"),
                                        Location       = GetStringProperty(item, "location"),
                                        Recommendation = GetStringProperty(item, "recommendation")
                                    }
                                );
                            }
                        }
                    }
                }

                if (root.TryGetProperty("errors", out var errorsElement)) {
                    if (errorsElement.ValueKind is JsonValueKind.Array) {
                        foreach (var item in errorsElement.EnumerateArray()) {
                            if (item.ValueKind is JsonValueKind.String) {
                                result.Errors.Add(
                                    new CheckResult.CheckIssue {
                                        Code           = "GENERIC_ERROR",
                                        Message        = item.GetString() ?? "",
                                        Location       = null,
                                        Recommendation = null
                                    }
                                );
                            }
                            else if (item.ValueKind is JsonValueKind.Object) {
                                result.Errors.Add(
                                    new CheckResult.CheckIssue {
                                        Code           = GetStringProperty(item, "code"),
                                        Message        = GetStringProperty(item, "message"),
                                        Location       = GetStringProperty(item, "location"),
                                        Recommendation = GetStringProperty(item, "recommendation")
                                    }
                                );
                            }
                        }
                    }
                }

                if (root.TryGetProperty("flagged_fragments", out var flaggedElement)) {
                    if (flaggedElement.ValueKind is JsonValueKind.Array) {
                        foreach (var item in flaggedElement.EnumerateArray()) {
                            if (item.ValueKind is JsonValueKind.Object) {
                                result.FlaggedFragments.Add(
                                    new CheckResult.FlaggedFragment {
                                        Fragment       = GetStringProperty(item, "fragment")
                                                         ?? GetStringProperty(item, "text"),
                                        RiskType       = GetStringProperty(item, "risk_type"),
                                        Reason         = GetStringProperty(item, "reason"),
                                        Recommendation = GetStringProperty(item, "recommendation")
                                    }
                                );
                            }
                        }
                    }
                }

                return result;
            }
            catch {
                return new CheckResult {
                    CheckId          = checkId,
                    Status           = "error",
                    RiskLevel        = "high",
                    Summary          = $"Критическая ошибка парсинга JSON. Исходное сообщение: {ex.Message}",
                    Warnings         = new List<CheckResult.CheckIssue>(),
                    Errors           = new List<CheckResult.CheckIssue>(),
                    FlaggedFragments = new List<CheckResult.FlaggedFragment>(),
                    AuthorComment    = "Автоматическая проверка завершилась с ошибкой.",
                    EditorComment    = "Модель вернула невалидный JSON. Требуется ручная проверка."
                };
            }
        }

        return new CheckResult {
            CheckId          = checkId,
            Status           = "error",
            RiskLevel        = "high",
            Summary          = "Ошибка: модель вернула пустой ответ",
            Warnings         = new List<CheckResult.CheckIssue>(),
            Errors           = new List<CheckResult.CheckIssue>(),
            FlaggedFragments = new List<CheckResult.FlaggedFragment>(),
            AuthorComment    = "Автоматическая проверка завершилась с ошибкой.",
            EditorComment    = "Модель вернула невалидный JSON. Требуется ручная проверка."
        };
    }

    private static string? GetStringProperty(JsonElement element, string propertyName) {
        if (element.TryGetProperty(propertyName, out var prop) && prop.ValueKind is JsonValueKind.String)
            return prop.GetString();
        return null;
    }

    private static double? GetDoubleProperty(JsonElement element, string propertyName) {
        if (element.TryGetProperty(propertyName, out var prop) && prop.ValueKind is JsonValueKind.Number)
            return prop.GetDouble();
        return null;
    }
}
