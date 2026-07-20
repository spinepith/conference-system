using System.CommandLine;

using DotNetEnv;

using ContentValidation.Core;


LoadEnvFile();

var rootCommand = new RootCommand("ContentValidation.Cli - Модуль автоматической валидации материалов");

var submissionIdArg = new Argument<string>(
    name: "submission-id",
    description: "ID материала (например: SUB-2026-Q1-00001)"
);

var apiKeyOption = new Option<string?>(
    name: "--api-key",
    description: "API ключ Gemini (по умолчанию из переменной  TOKEN)",
    getDefaultValue: () => Environment.GetEnvironmentVariable("TOKEN")
);

var storageOption = new Option<string?>(
    name: "--storage",
    description: "Путь к storage (по умолчанию из переменной PATH_STORAGE)",
    getDefaultValue: () => Environment.GetEnvironmentVariable("PATH_STORAGE")
);

var promptsOption = new Option<string>(
    name: "--prompts",
    description: "Путь к промптам",
    getDefaultValue: () => "Prompts"
);

var modelOption = new Option<string>(
    name: "--model",
    description: "Модель Gemini",
    getDefaultValue: () => Environment.GetEnvironmentVariable("LLM_MODEL") ?? "gemini-3.1-flash-lite"
);

rootCommand.AddArgument(submissionIdArg);
rootCommand.AddOption(apiKeyOption);
rootCommand.AddOption(storageOption);
rootCommand.AddOption(promptsOption);
rootCommand.AddOption(modelOption);

rootCommand.SetHandler(async (submissionId, apiKey, storage, prompts, model) => {
    try {
        if (string.IsNullOrEmpty(apiKey)) {
            Console.Error.WriteLine("ОШИБКА: API ключ не найден. Установите переменную TOKEN, либо передайте через --api-key");
            Environment.Exit(1);
        }

        if (string.IsNullOrEmpty(storage)) {
            Console.Error.WriteLine("ОШИБКА: Путь к storage не найден. Установите переменную PATH_STORAGE, либо передайте через --storage");
            Environment.Exit(1);
        }

        if (!Directory.Exists(storage)) {
            Console.Error.WriteLine($"ОШИБКА: Папка storage не существует: {storage}");
            Environment.Exit(1);
        }

        var submissionPath = Path.Combine(storage, "submissions", submissionId);
        if (!Directory.Exists(submissionPath)) {
            Console.Error.WriteLine($"ОШИБКА: Папка материала не существует: {submissionPath}");
            Environment.Exit(1);
        }

        var metadataPath = Path.Combine(submissionPath, "extracted_metadata.json");
        if (!File.Exists(metadataPath)) {
            Console.Error.WriteLine($"ОШИБКА: Файл extracted_metadata.json не найден: {metadataPath}");
            Environment.Exit(1);
        }

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

        Console.WriteLine($"Запуск валидации для: {submissionId}");
        Console.WriteLine($"Модель: {model}");
        await validator.CheckAsync(submissionId);

        var checkResultPath = Path.Combine(submissionPath, "check_result.json");
        if (!File.Exists(checkResultPath)) {
            Console.Error.WriteLine("ОШИБКА: Валидация не создала check_result.json");
            Environment.Exit(1);
        }

        Console.WriteLine("Валидация завершена");
        Environment.Exit(0);
    }
    catch (Exception ex) {
        Console.Error.WriteLine($"ОШИБКА: {ex.Message}");
        Console.Error.WriteLine(ex.StackTrace);
        Environment.Exit(1);
    }
}, submissionIdArg, apiKeyOption, storageOption, promptsOption, modelOption);

return await rootCommand.InvokeAsync(args);


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
