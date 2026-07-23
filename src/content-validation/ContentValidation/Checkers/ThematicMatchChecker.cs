using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class ThematicMatchChecker : BaseChecker {
    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        return await ExecuteCheckAsync(checkId, title, "ThematicMatch.txt", text);
    }
}
