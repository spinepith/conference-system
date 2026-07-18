using ContentValidation.Core;
using ContentValidation.Models;
using ContentValidation.Services;


namespace ContentValidation;

public class ContentValidation {
    private readonly FileService _fileService;
    private readonly CheckService _checkService;
    private readonly LlmClient _llmClient;
    private readonly string _promptsPath;

    public ContentValidation(LlmClient llmClient, string storagePath, string promptsPath = "Prompts", string logFile = "llm_calls.log") {
        _fileService  = new FileService(storagePath);
        _checkService = new CheckService();
        _llmClient    = llmClient;
        _promptsPath  = promptsPath;
    }

    public async Task CheckAsync(string submissionId) {
        try {
            var path = Environment.GetEnvironmentVariable("PATH_STORAGE");
            if (string.IsNullOrEmpty(path)) {
                await SaveErrorResult(submissionId, "Переменная среды PATH_STORAGE не найдена или пуста");
                return;
            }

            path = Path.Combine(path, "submissions", submissionId, "extracted_metadata.json");
            var materialData = await _fileService.GetMaterialDataAsync(path);
            if (materialData is null) {
                await SaveErrorResult(submissionId, "Файл extracted_metadata.json не найден");
                return;
            }

            var logger = new ValidationLogger(submissionId);

            var llmService = new LlmService(_llmClient, _promptsPath, logger);
            BaseChecker.Initialize(llmService);

            var results = await _checkService.RunAllChecksAsync(submissionId, materialData);

            foreach (var result in results.checkResults)
                await _fileService.SaveCheckResultAsync(submissionId, result);
            await _fileService.SaveFinalResultAsync(submissionId, results.finalResult);
        }
        catch (Exception ex) {
            await SaveErrorResult(submissionId, $"Критическая ошибка при выполнении проверок: {ex.Message}");
        }
    }

    public async Task<string> CheckAsync(string path, string filename) {
        try {
            var materialData = await _fileService.GetMaterialDataAsync(Path.Combine(path, filename));
            if (materialData is null)
                return CreateErrorJson($"Файл метаданных не найден или некорректен. {{ path: {path}, {filename} }}");

            var logger = new ValidationLogger(path);
            var llmService = new LlmService(_llmClient, _promptsPath, logger);

            BaseChecker.Initialize(llmService);

            var checksResult = await _checkService.RunAllChecksAsync(path, materialData);

            foreach (var checkResult in checksResult.checkResults)
                await _fileService.SaveCheckResultAsync(path, checkResult);
            await _fileService.SaveFinalResultAsync(path, checksResult.finalResult);

            return System.Text.Json.JsonSerializer.Serialize(
                checksResult.checkResults,
                new System.Text.Json.JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }
            );
        }
        catch (Exception ex) {
            return CreateErrorJson(ex.Message);
        }
    }

    private async Task SaveErrorResult(string submissionId, string errorMessage) {
        try {
            var errorResult = new CheckResult {
                CheckId          = "system_error",
                Title            = "Системная ошибка",
                Status           = "error",
                RiskLevel        = "high",
                Score            = 0.0,
                Summary          = errorMessage,
                Warnings         = new List<CheckResult.CheckIssue>(),
                Errors           = new List<CheckResult.CheckIssue>(),
                FlaggedFragments = new List<CheckResult.FlaggedFragment>(),
                AuthorComment    = "Автоматическая проверка не может быть выполнена",
                EditorComment    = "Требуется ручная проверка материала",
                RawModelResponse = null
            };

            var errorResults = new List<CheckResult> { errorResult };
            var finalResult = FinalResult.Create(
                Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!, "submissions", submissionId, "check_result.json"),
                submissionId,
                errorResults
            );

            await _fileService.SaveCheckResultAsync(submissionId, errorResult);
            await _fileService.SaveFinalResultAsync(submissionId, finalResult);
        }
        catch { }
    }

    private string CreateErrorJson(string errorMessage) {
        var errorData = new {
            message = errorMessage,
            timestamp = DateTime.UtcNow.ToString("o")
        };
        return System.Text.Json.JsonSerializer.Serialize(
            errorData, new System.Text.Json.JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }
        );
    }
}
