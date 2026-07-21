using System.CommandLine;

using ContentValidation.Core;


var rootCommand = new RootCommand("ContentValidation.Cli - Модуль автоматической валидации материалов");

var cliOptions = new SharedCliOptions();
cliOptions.ApplyTo(rootCommand);

var submissionIdArg = new Argument<string>("submission-id", "ID материала (например: SUB-2026-Q1-00001)");
rootCommand.AddArgument(submissionIdArg);

rootCommand.SetHandler(async (submissionId, envPath, apiKey, storage, prompts, model) => {
    var config = cliOptions.GetConfig(envPath, apiKey, storage, prompts, model);

    var submissionPath = Path.Combine(config.StoragePath, "submissions", submissionId);
    if (!Directory.Exists(submissionPath)) {
        Console.Error.WriteLine($"ОШИБКА: Папка материала не существует: {submissionPath}");
        Environment.Exit(1);
    }

    var metadataPath = Path.Combine(submissionPath, "extracted_metadata.json");
    if (!File.Exists(metadataPath)) {
        Console.Error.WriteLine($"ОШИБКА: Файл extracted_metadata.json не найден: {metadataPath}");
        Environment.Exit(1);
    }

    var llmClient = new LlmClient(config.ApiKey, config.Model);
    var validator = new ContentValidation.ContentValidation(llmClient, config.StoragePath, config.PromptsPath);

    Console.WriteLine($"Запуск валидации для: {submissionId}");
    Console.WriteLine($"Модель: {config.Model}");
    await validator.CheckAsync(submissionId);

    var checkResultPath = Path.Combine(submissionPath, "check_result.json");
    if (!File.Exists(checkResultPath)) {
        Console.Error.WriteLine("ОШИБКА: Валидация не создала check_result.json");
        Environment.Exit(1);
    }

    Console.WriteLine("Валидация завершена");
    Environment.Exit(0);
},
submissionIdArg, cliOptions.EnvOption, cliOptions.ApiKeyOption, cliOptions.StorageOption, cliOptions.PromptsOption, cliOptions.ModelOption);

return await rootCommand.InvokeAsync(args);