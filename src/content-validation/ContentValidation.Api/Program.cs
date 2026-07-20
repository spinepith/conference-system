using DotNetEnv;

using ContentValidation.Core;


LoadEnvFile();

var apiKey = Environment.GetEnvironmentVariable("TOKEN");
if (string.IsNullOrEmpty(apiKey)) {
    Console.Error.WriteLine("ОШИБКА: API ключ не найден. Установите переменную TOKEN в .env файле");
    Environment.Exit(1);
}

var storage = Environment.GetEnvironmentVariable("PATH_STORAGE");
if (string.IsNullOrEmpty(storage)) {
    Console.Error.WriteLine("ОШИБКА: Путь к storage не найден. Установите переменную PATH_STORAGE в .env файле");
    Environment.Exit(1);
}

if (!Directory.Exists(storage)) {
    Console.Error.WriteLine($"ОШИБКА: Папка storage не существует: {storage}");
    Environment.Exit(1);
}

var model = Environment.GetEnvironmentVariable("LLM_MODEL") ?? "gemini-3.1-flash-lite";
var prompts = "Prompts";

var absolutePromptsPath = prompts;
if (!Path.IsPathRooted(prompts)) {
    var exeDir = AppContext.BaseDirectory;
    absolutePromptsPath = Path.Combine(exeDir, prompts);
}

if (!Directory.Exists(absolutePromptsPath)) {
    Console.Error.WriteLine($"ОШИБКА: Папка с промптами не найдена: {absolutePromptsPath}");
    Environment.Exit(1);
}

var llmClient = new LlmClient(apiKey, model);
var validator = new ContentValidation.ContentValidation(llmClient, storage, absolutePromptsPath);

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapPost("/validate", async (ValidationRequest request) => {
    try {
        var submissionId = request.SubmissionId;

        if (string.IsNullOrEmpty(submissionId)) {
            return Results.Json(
                new {
                    status = "error",
                    message = "submission_id обязателен"
                },
                statusCode: 400
            );
        }

        var submissionPath = Path.Combine(storage, "submissions", submissionId);
        if (!Directory.Exists(submissionPath)) {
            return Results.Json(
                new {
                    status = "error",
                    submission_id = submissionId,
                    message = $"Папка материала не существует: {submissionPath}"
                },
                statusCode: 404
            );
        }

        var metadataPath = Path.Combine(submissionPath, "extracted_metadata.json");
        if (!File.Exists(metadataPath)) {
            return Results.Json(
                new {
                    status = "error",
                    submission_id = submissionId,
                    message = $"Файл extracted_metadata.json не найден: {metadataPath}"
                },
                statusCode: 404
            );
        }

        Console.WriteLine($"Запуск валидации для: {submissionId}");
        Console.WriteLine($"Модель: {model}");

        await validator.CheckAsync(submissionId);

        var checkResultPath = Path.Combine(submissionPath, "check_result.json");
        if (!File.Exists(checkResultPath)) {
            return Results.Json(
                new {
                    status = "error",
                    submission_id = submissionId,
                    message = "Валидация не создала check_result.json"
                },
                statusCode: 500
            );
        }

        Console.WriteLine("Валидация завершена");

        return Results.Ok(
            new {
                status = "success",
                submission_id = submissionId,
                message = "Валидация завершена"
            }
        );
    }
    catch (Exception ex) {
        Console.Error.WriteLine($"ОШИБКА: {ex.Message}");
        Console.Error.WriteLine(ex.StackTrace);

        return Results.Json(
            new {
                status = "error",
                submission_id = request.SubmissionId,
                message = ex.Message
            },
            statusCode: 500
        );
    }
});

app.MapGet("/health", () => Results.Ok(
    new {
        status = "ok",
        service = "ContentValidation.Api",
        model = model,
        storage = storage,
        prompts = absolutePromptsPath,
        timestamp = DateTime.UtcNow
    }
));

app.MapGet("/", () => Results.Text(
    """
    ContentValidation.Api - HTTP сервис автоматической валидации материалов

    Доступные endpoints:
    - GET  /health     - Проверка состояния сервиса
    - POST /validate   - Валидация материала

    Пример POST запроса:
    curl -X POST http://localhost:5100/validate \
         -H "Content-Type: application/json" \
         -d '{"submissionId":"SUB-2026-Q1-00001"}'
    """,
    "text/plain",
    System.Text.Encoding.UTF8
));

Console.WriteLine("ContentValidation.Api - HTTP сервис автоматической валидации материалов");
Console.WriteLine($"URL: http://localhost:5100");
Console.WriteLine($"Модель: {model}");
Console.WriteLine($"Storage: {storage}");
Console.WriteLine($"Prompts: {absolutePromptsPath}");
Console.WriteLine();

app.Run("http://0.0.0.0:5100");

static void LoadEnvFile() {
    var current = new DirectoryInfo(Directory.GetCurrentDirectory());

    while (current is not null) {
        var envPath = Path.Combine(current.FullName, ".env");
        if (File.Exists(envPath)) {
            Env.Load(envPath);
            return;
        }
        current = current.Parent;
    }
}

record ValidationRequest(string SubmissionId);