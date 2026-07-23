using System.Text.Json.Serialization;


namespace ContentValidation.Models;

public class FinalResult {
    [JsonPropertyName("submission_id")]
    public string? SubmissionId       { get; set; }

    [JsonPropertyName("checked_at")]
    public string? CheckedAt          { get; set; }

    [JsonPropertyName("overall_status")]
    public string? OverallStatus      { get; set; }

    [JsonPropertyName("overall_risk_level")]
    public string? OverallRiskLevel   { get; set; }

    [JsonPropertyName("checks")]
    public List<CheckSummary>? Checks { get; set; }

    [JsonPropertyName("author_message")]
    public string? AuthorMessage      { get; set; }

    [JsonPropertyName("editor_message")]
    public string? EditorMessage      { get; set; }

    [JsonPropertyName("report_path")]
    public string? ReportPath         { get; set; }

    public class CheckSummary {
        [JsonPropertyName("check_id")]
        public string? CheckId   { get; set; }

        [JsonPropertyName("title")]
        public string? Title     { get; set; }

        [JsonPropertyName("status")]
        public string? Status    { get; set; }

        [JsonPropertyName("risk_level")]
        public string? RiskLevel { get; set; }

        [JsonPropertyName("summary")]
        public string? Summary   { get; set; }
    }

    public static FinalResult Create(string path, string submissionId, List<CheckResult> results) {
        int passed   = 0;
        int warnings = 0;
        int failed   = 0;
        int errors   = 0;

        foreach (var item in results) {
            if (item.Status is "passed")
                passed++;
            else if (item.Status is "warning")
                warnings++;
            else if (item.Status is "failed")
                failed++;
            else if (item.Status is "error")
                errors++;
        }

        string overallStatus;
        string overallRiskLevel;

        if (errors > 0 || failed > 0) {
            overallStatus    = "failed";
            overallRiskLevel = "high";
        }
        else if (warnings > 0) {
            overallStatus    = "needs_attention";
            overallRiskLevel = "medium";
        }
        else {
            overallStatus    = "passed";
            overallRiskLevel = "low";
        }

        var authorMessages = new List<string>();
        var editorMessages = new List<string>();

        foreach (var item in results) {
            if (!string.IsNullOrEmpty(item.AuthorComment))
                authorMessages.Add(item.AuthorComment);
            if (!string.IsNullOrEmpty(item.EditorComment))
                editorMessages.Add(item.EditorComment);
        }

        var checks = new List<CheckSummary>();
        foreach (var item in results) {
            checks.Add(
                new CheckSummary {
                    CheckId   = item.CheckId,
                    Title     = item.Title,
                    Status    = item.Status,
                    RiskLevel = item.RiskLevel,
                    Summary   = item.Summary
                }
            );
        }

        return new FinalResult {
            SubmissionId     = submissionId,
            CheckedAt        = DateTime.UtcNow.ToString("o"),
            OverallStatus    = overallStatus,
            OverallRiskLevel = overallRiskLevel,
            Checks           = checks,
            AuthorMessage    = string.Join(" ", authorMessages),
            EditorMessage    = string.Join(" ", editorMessages),
            ReportPath       = path
        };
    }
}
