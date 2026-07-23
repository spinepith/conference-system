using System;
using System.CommandLine;
using System.IO;

using DotNetEnv;


public record AppConfig(string ApiKey, string StoragePath, string PromptsPath, string Model);

public class SharedCliOptions {
    public Option<string?> EnvOption     { get; } = new(name: "--env",     description: "Путь к .env файлу");
    public Option<string?> ApiKeyOption  { get; } = new(name: "--api-key", description: "API ключ Gemini");
    public Option<string?> StorageOption { get; } = new(name: "--storage", description: "Путь к storage");
    public Option<string> PromptsOption  { get; } = new(name: "--prompts", description: "Путь к промптам");
    public Option<string> ModelOption    { get; } = new(name: "--model",   description: "Модель Gemini");

    public void ApplyTo(Command command) {
        command.AddOption(EnvOption);
        command.AddOption(ApiKeyOption);
        command.AddOption(StorageOption);
        command.AddOption(PromptsOption);
        command.AddOption(ModelOption);
    }

    public AppConfig GetConfig(string? envPath, string? apiKey, string? storage, string? prompts, string? model) {
        LoadEnvFile(envPath);

        apiKey  ??= Environment.GetEnvironmentVariable("API_KEY");
        storage ??= Environment.GetEnvironmentVariable("PATH_STORAGE");
        model   ??= Environment.GetEnvironmentVariable("LLM_MODEL") ?? "gemini-3.1-flash-lite";
        prompts ??= "Prompts";

        if (string.IsNullOrEmpty(apiKey)) {
            Console.Error.WriteLine("ОШИБКА: API ключ не найден. Установите переменную API_KEY, либо передайте через --api-key");
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

        var absolutePromptsPath = Path.IsPathRooted(prompts) ? prompts : Path.Combine(AppContext.BaseDirectory, prompts);
        if (!Directory.Exists(absolutePromptsPath)) {
            Console.Error.WriteLine($"ОШИБКА: Папка с промптами не найдена: {absolutePromptsPath}");
            Environment.Exit(1);
        }

        return new AppConfig(apiKey, storage, absolutePromptsPath, model);
    }

    private static void LoadEnvFile(string? customPath) {
        if (!string.IsNullOrEmpty(customPath)) {
            if (File.Exists(customPath)) {
                Env.Load(customPath);
                return;
            }
            Console.Error.WriteLine($"ПРЕДУПРЕЖДЕНИЕ: Указанный .env файл не найден: {customPath}");
        }

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null) {
            var envPath = Path.Combine(current.FullName, ".env");
            if (File.Exists(envPath)) {
                Env.Load(envPath);
                return;
            }
            current = current.Parent;
        }
    }
}