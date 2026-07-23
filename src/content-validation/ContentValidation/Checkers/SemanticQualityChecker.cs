using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class SemanticQualityChecker : BaseChecker {
    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        return await ExecuteCheckAsync(checkId, title, "SemanticQuality.txt", text);
    }
}
