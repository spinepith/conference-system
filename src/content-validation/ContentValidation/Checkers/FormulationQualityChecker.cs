using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class FormulationQualityChecker : BaseChecker {
    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        return await ExecuteCheckAsync(checkId, title, "FormulationQuality.txt", text);
    }
}