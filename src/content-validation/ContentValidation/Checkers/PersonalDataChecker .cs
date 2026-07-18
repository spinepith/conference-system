using System.Text.RegularExpressions;
using ContentValidation.Models;


namespace ContentValidation.Checkers;

internal class PersonalDataChecker : BaseChecker {
    private static readonly Regex EmailRegex    = new(@"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", RegexOptions.Compiled);
    private static readonly Regex PhoneRegex    = new(@"(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", RegexOptions.Compiled);
    private static readonly Regex PassportRegex = new(@"\b\d{4}\s*№?\s*\d{6}\b", RegexOptions.Compiled);
    private static readonly Regex SnilsRegex    = new(@"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b", RegexOptions.Compiled);
    private static readonly Regex InnRegex      = new(@"\b\d{10,12}\b", RegexOptions.Compiled);
    private static readonly Regex AddressRegex  = new(@"(?:ул\.|улица|пр\.|проспект|пер\.|переулок)[\s]+[А-Яа-яЁё\s]+,?\s*д\.?\s*\d+", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    internal static async Task<CheckResult> CheckAsync(string checkId, string title, string text) {
        try {
            var regexFindings = PerformRegexCheck(text);
            var llmResult = await ExecuteCheckAsync(checkId, title, "PersonalData.txt", text);

            return MergeResults(llmResult, regexFindings);
        }
        catch {
            return await ExecuteCheckAsync(checkId, title, "PersonalData.txt", text);
        }
    }

    private static List<CheckResult.FlaggedFragment> PerformRegexCheck(string text) {
        var findings = new List<CheckResult.FlaggedFragment>();

        var emails = EmailRegex.Matches(text);
        foreach (Match match in emails) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "contact_info",
                    Reason         = "Обнаружен email-адрес, который может быть персональным контактом третьего лица",
                    Recommendation = "Проверить, является ли это официальным контактом автора или персональными данными"
                }
            );
        }

        var phones = PhoneRegex.Matches(text);
        foreach (Match match in phones) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "contact_info",
                    Reason         = "Обнаружен номер телефона",
                    Recommendation = "Убедиться, что это официальный контакт, а не личный номер"
                }
            );
        }

        var passports = PassportRegex.Matches(text);
        foreach (Match match in passports) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "personal_data",
                    Reason         = "Обнаружена последовательность, похожая на серию и номер паспорта",
                    Recommendation = "КРИТИЧНО: Удалить паспортные данные перед публикацией"
                }
            );
        }

        var snils = SnilsRegex.Matches(text);
        foreach (Match match in snils) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "personal_data",
                    Reason         = "Обнаружена последовательность, похожая на номер СНИЛС",
                    Recommendation = "КРИТИЧНО: Удалить СНИЛС перед публикацией"
                }
            );
        }

        var inns = InnRegex.Matches(text);
        foreach (Match match in inns) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "personal_data",
                    Reason         = "Обнаружен ИНН",
                    Recommendation = "Проверить необходимость публикации ИНН"
                }
            );
        }

        var addresses = AddressRegex.Matches(text);
        foreach (Match match in addresses) {
            findings.Add(
                new CheckResult.FlaggedFragment {
                    Fragment       = match.Value,
                    RiskType       = "personal_data",
                    Reason         = "Обнаружен адрес, который может быть персональными данными",
                    Recommendation = "Проверить, является ли это адресом организации или личным адресом"
                }
            );
        }

        return findings;
    }

    private static CheckResult MergeResults(CheckResult llmResult, List<CheckResult.FlaggedFragment> regexFindings) {
        try {
            var allFragments = new List<CheckResult.FlaggedFragment>();
            if (llmResult.FlaggedFragments is not null)
                allFragments.AddRange(llmResult.FlaggedFragments);

            allFragments.AddRange(regexFindings);

            var uniqueFragments = allFragments.GroupBy(f => f.Fragment).Select(g => g.First()).ToList();
            llmResult.FlaggedFragments = uniqueFragments;

            if (regexFindings.Any(f => f.RiskType is "personal_data")) {
                llmResult.RiskLevel = "high";
                llmResult.Status = "warning";
            }

            if (uniqueFragments.Count > 0) {
                llmResult.Summary =
                    $"Обнаружено {uniqueFragments.Count} фрагмент(ов), требующих проверки. " +
                    $"Регулярные выражения: {regexFindings.Count}, AI-анализ: {(llmResult.FlaggedFragments?.Count ?? 0) - regexFindings.Count}";
            }

            return llmResult;
        }
        catch { return llmResult; }
    }
}
