using ContentValidation.Checkers;
using ContentValidation.Models;


namespace ContentValidation.Services;

internal class CheckService {
    internal async Task<(List<CheckResult> checkResults, FinalResult finalResult)> RunAllChecksAsync(string submissionId, MaterialData materialData) {
        var logger = new ValidationLogger(submissionId);
        var startTime = DateTime.UtcNow;

        logger.Info($"Начало валидации для {submissionId}");
        logger.Info($"Материал: \"{materialData.Title}\"");

        try {
            var fullText = BuildFullText(materialData);
            logger.Info($"Длина полного текста: {fullText.Length} символов");
            logger.Info("Запуск 6 параллельных проверок");
            var checkTasks = new List<Task<CheckResult>> {
                FormulationQualityChecker.CheckAsync("formulation_quality_check",    "Проверка качества формулировок",      fullText),
                PersonalDataChecker.CheckAsync("personal_data_check",                "Проверка на чувствительные сведения", fullText),
                RestrictedContentChecker.CheckAsync("restricted_content_check",      "Проверка на недопустимое содержание", fullText),
                ScientificStructureChecker.CheckAsync("scientific_structure_check",  "Проверка научной структуры",          fullText),
                SemanticQualityChecker.CheckAsync("semantic_quality_check",          "Смысловая проверка материала",        fullText),
                ThematicMatchChecker.CheckAsync("thematic_match_check",              "Проверка тематического соответствия", fullText)
            };

            var results = new List<CheckResult>(await Task.WhenAll(checkTasks));

            var duration = (DateTime.UtcNow - startTime).TotalSeconds;
            logger.Info($"Все проверки завершены за {duration:F1} секунд");

            var finalResult = FinalResult.Create(Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!, "submissions", submissionId, "check_result.json"), submissionId, results);

            logger.Info($"Общий статус: {finalResult.OverallStatus}");
            logger.Info($"Общий уровень риска: {finalResult.OverallRiskLevel}");

            var passed   = results.Count(r => r.Status == "passed");
            var warnings = results.Count(r => r.Status == "warning");
            var failed   = results.Count(r => r.Status == "failed" || r.Status == "error");

            logger.Info($"Результаты: успешно={passed}, предупреждения={warnings}, ошибки={failed}");
            logger.Info("Валидация завершена успешно");

            return (results, finalResult);
        }
        catch (Exception ex) {
            logger.Error("Критическая ошибка при валидации", ex);
            var errorResult = new CheckResult {
                CheckId          = "system_error",
                Title            = "Системная ошибка",
                Status           = "error",
                RiskLevel        = "high",
                Score            = 0.0,
                Summary          = "Произошла критическая ошибка при выполнении проверок",
                Warnings         = new List<CheckResult.CheckIssue>(),
                Errors           = new List<CheckResult.CheckIssue>(),
                FlaggedFragments = new List<CheckResult.FlaggedFragment>(),
                AuthorComment    = "Автоматическая проверка временно недоступна",
                EditorComment    = "Требуется ручная проверка всех аспектов материала",
                RawModelResponse = null
            };

            var errorResults = new List<CheckResult> { errorResult };
            return (errorResults, FinalResult.Create(Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!, "submissions", submissionId, "check_result.json"), submissionId, errorResults));
        }
    }

    private string BuildFullText(MaterialData materialData) {
        try {
            var text = new System.Text.StringBuilder();

            if (!string.IsNullOrEmpty(materialData.Title))
                text.Append($"Название: {materialData.Title}\n\n");

            if (materialData.Authors is not null && materialData.Authors.Count > 0)
                text.Append($"Авторы: {string.Join(", ", materialData.Authors)}\n\n");

            if (!string.IsNullOrEmpty(materialData.Organization))
                text.Append($"Организация: {materialData.Organization}\n\n");

            if (!string.IsNullOrEmpty(materialData.Abstract))
                text.Append($"Аннотация: {materialData.Abstract}\n\n");

            if (materialData.Keywords is not null && materialData.Keywords.Count > 0)
                text.Append($"Ключевые слова: {string.Join(", ", materialData.Keywords)}\n\n");

            if (!string.IsNullOrEmpty(materialData.BodyText))
                text.Append($"Основной текст:\n{materialData.BodyText}\n\n");

            if (materialData.References is not null && materialData.References.Count > 0)
                text.Append($"Список литературы:\n{string.Join("\n", materialData.References)}");

            return text.ToString();
        }
        catch {
            return "Ошибка формирования текста материала";
        }
    }
}
