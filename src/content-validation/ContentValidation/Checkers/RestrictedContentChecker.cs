using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class RestrictedContentChecker : BaseChecker {
    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        return await ExecuteCheckAsync(checkId, title, "RestrictedContent.txt", text);
    }
}
