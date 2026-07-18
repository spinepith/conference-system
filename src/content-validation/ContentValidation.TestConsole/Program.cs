using DotNetEnv;
using ContentValidation.Core;


namespace ContentValidation.TestConsole;

public class Program {
    public static async Task Main(string[] args) {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, ".env.example")))
            dir = dir.Parent;
        if (dir is not null)
            Env.Load(Path.Combine(dir.FullName, ".env"));

        #region SETUP
        Console.InputEncoding  = System.Text.Encoding.UTF8;
        Console.OutputEncoding = System.Text.Encoding.UTF8;

        var apiKey = Environment.GetEnvironmentVariable("TOKEN")!;
        var useJsonInput = false;

        var llmClient = new LlmClient(apiKey, "gemini-3.1-flash-lite");
        var validator = new ContentValidation(llmClient, Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!));
        #endregion

        Console.Clear();
        Console.WriteLine("### CONTENT VALIDATION DEBUG ###\n");
        Console.WriteLine("★ ──────────────────────────────────────────────────────────────┐");
        Console.WriteLine("│  - /id   <имя>   - проверить файл по submission-id из storage │");
        Console.WriteLine("│  - /file <путь>  - проверить текст из файла                   │");
        Console.WriteLine("│  - /exit         - выход                                      │");
        Console.WriteLine("└───────────────────────────────────────────────────────────────┘");
        //Console.WriteLine("│  - /test        - проверки из папки Tests     │");

        CancellationTokenSource cts = new CancellationTokenSource();
        Console.CancelKeyPress += (sender, e) => {
            e.Cancel = true;
            Exit();
        };

        void Exit() {
            cts.Cancel();
            Console.WriteLine();
            Console.WriteLine("ЗАВЕРШЕНИЕ РАБОТЫ...");
            Environment.Exit(0);
        }

        while (!cts.Token.IsCancellationRequested) {
            try {
                Console.WriteLine();
                Console.Write("> ");

                string input = Console.ReadLine() ?? "";

                if (string.IsNullOrWhiteSpace(input))
                    continue;

                if (input.Trim().ToLower() is "/exit")
                    Exit();

                else if (input.Trim().StartsWith("/id ")) {
                    var filePath = Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!, "submissions", input.Substring(4).Trim(), "extracted_metadata.json");

                    if (!File.Exists(filePath)) {
                        Console.WriteLine($"# ОШИБКА: ФАЙЛ НЕ НАЙДЕН: {filePath}");
                        continue;
                    }

                    useJsonInput = true;
                    input = filePath;
                }

                else if (input.Trim().StartsWith("/file ")) {
                    var filePath = input.Substring(6).Trim();

                    if (!File.Exists(filePath)) {
                        Console.WriteLine($"# ОШИБКА: ФАЙЛ НЕ НАЙДЕН: {filePath}");
                        continue;
                    }

                    useJsonInput = true;
                    input = Path.Combine(Environment.GetEnvironmentVariable("PATH_STORAGE")!, "submissions", Path.GetFileNameWithoutExtension(filePath), "extracted_metadata.json");
                }

                Console.WriteLine();
                Console.WriteLine("# ОБРАБОТКА...");
                Console.WriteLine();

                var result = string.Empty;
                if (useJsonInput)
                    result = await validator.CheckAsync(Path.GetDirectoryName(input) ?? "", Path.GetFileName(input));
                else
                    result = await llmClient.SendRequestAsync("", input);

                Console.WriteLine($"# РЕЗУЛЬТАТ\n{result}");
            }
            catch (Exception ex) {
                Console.WriteLine($"# ОШИБКА: {ex.Message}");
            }
        }

        Console.WriteLine();
        Console.WriteLine("ПРОГРАММА ЗАВЕШЕНА.");
    }
}
