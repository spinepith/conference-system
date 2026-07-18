using System.Text.Json;
using System.Text.Encodings.Web;
using ContentValidation.Models;


namespace ContentValidation.Services;

internal class FileService {
    private readonly string _storagePath;
    private readonly JsonSerializerOptions _jsonOptions;

    internal FileService(string storagePath) {
        _storagePath = storagePath;
        _jsonOptions = new JsonSerializerOptions {
            WriteIndented = true,
            Encoder       = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
        };
    }

    internal Task SaveCheckResultAsync(string submissionId, CheckResult result) => Save(Path.Combine(_storagePath, "submissions", submissionId, "checks"), $"{result.CheckId}.json", result);
    internal Task SaveFinalResultAsync(string submissionId, FinalResult result) => Save(Path.Combine(_storagePath, "submissions", submissionId), "check_result.json", result);

    private async Task Save<T>(string path, string file, T result) {
        try {
            Directory.CreateDirectory(path);
            var filePath = Path.Combine(path, file);
            var json = JsonSerializer.Serialize(result, _jsonOptions);
            await File.WriteAllTextAsync(filePath, json);
        }
        catch { }
    }

    internal async Task<MaterialData?> GetMaterialDataAsync(string filePath) {
        try {
            if (!File.Exists(filePath))
                return null;

            string json = await File.ReadAllTextAsync(filePath);
            return JsonSerializer.Deserialize<MaterialData>(json, _jsonOptions);
        }
        catch { return null; }
    }
}
