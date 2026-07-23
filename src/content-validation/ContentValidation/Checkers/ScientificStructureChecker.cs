using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class ScientificStructureChecker : BaseChecker {
    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        return await ExecuteCheckAsync(checkId, title, "ScientificStructure.txt", text);
    }
}
