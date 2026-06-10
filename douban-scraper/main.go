package main

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gocolly/colly"
)

const (
	BASE_URL  = "https://movie.douban.com/top250"
	MAX_DEPTH = 10
)

var (
	movies = make([]*Movie, 250)
	client = &http.Client{Timeout: 15 * time.Second}
)

type Movie struct {
	name   string
	link   string
	imdbId string
}

// 豆瓣 API 响应结构
type DoubanAPIResp struct {
	Subject struct {
		Title string `json:"title"`
		Year  string `json:"release_year"`
	} `json:"subject"`
}

// IMDB Suggestion API 响应结构
type IMDBSuggestion struct {
	D []struct {
		ID string `json:"id"`
		L  string `json:"l"`
		Y  int    `json:"y"`
	} `json:"d"`
}

func main() {
	// 第一步：爬取 Top250 列表
	c := colly.NewCollector(
		colly.MaxDepth(MAX_DEPTH),
		colly.Async(true),
		colly.UserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
	)

	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: MAX_DEPTH})

	c.OnHTML(".paginator > .next > a[href]", func(e *colly.HTMLElement) {
		e.Request.Visit(e.Request.AbsoluteURL(e.Attr("href")))
	})

	c.OnHTML("#content li", func(e *colly.HTMLElement) {
		index, err := strconv.Atoi(e.ChildText(".pic em"))
		if err != nil {
			return
		}
		movies[index-1] = &Movie{
			name: e.ChildAttr(".pic img", "alt"),
			link: e.ChildAttr(".info a", "href"),
		}
	})

	c.OnError(func(r *colly.Response, err error) {
		fmt.Printf("列表页请求失败: %s, error: %s\n", r.Request.URL, err)
	})

	c.Visit(BASE_URL)
	c.Wait()

	fmt.Println("✅ 列表爬取完成，开始获取 IMDB ID...")

	// 第二步：通过豆瓣 API + IMDB Suggestion API 获取 IMDB ID
	for i, movie := range movies {
		if movie == nil || movie.link == "" {
			continue
		}

		fmt.Printf("  [%d/%d] %s ... ", i+1, 250, movie.name)

		// 提取豆瓣 subject ID
		doubanId := extractDoubanId(movie.link)

		// 通过豆瓣 API 获取英文片名和年份
		enTitle, year := getDoubanInfo(doubanId)
		if enTitle == "" {
			fmt.Println("无法获取英文片名")
			continue
		}

		// 通过 IMDB Suggestion API 搜索
		imdbId := searchIMDB(enTitle, year)
		if imdbId != "" {
			movie.imdbId = imdbId
			fmt.Printf("IMDB: %s\n", imdbId)
		} else {
			fmt.Println("IMDB: 未找到")
		}

		time.Sleep(500 * time.Millisecond) // 避免请求过快
	}

	printResult()
	exportToCSV()
}

func extractDoubanId(link string) string {
	if idx := strings.Index(link, "/subject/"); idx != -1 {
		return strings.TrimRight(link[idx+len("/subject/"):], "/")
	}
	return ""
}

// 从豆瓣 API 获取英文片名和年份
func getDoubanInfo(doubanId string) (string, string) {
	apiUrl := fmt.Sprintf("https://movie.douban.com/j/subject_abstract?subject_id=%s", doubanId)
	req, _ := http.NewRequest("GET", apiUrl, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Referer", "https://movie.douban.com/")

	resp, err := client.Do(req)
	if err != nil {
		return "", ""
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var apiResp DoubanAPIResp
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return "", ""
	}

	title := apiResp.Subject.Title
	year := apiResp.Subject.Year

	// title 格式: "中文 English Name‎ (年份)"
	// 提取英文名
	enTitle := extractEnglishTitle(title)
	return enTitle, year
}

// 从 "中文 English Name‎ (年份)" 中提取英文名
func extractEnglishTitle(title string) string {
	// 去掉年份部分
	re := regexp.MustCompile(`\s*[\(（]\d{4}[\)）]\s*$`)
	title = re.ReplaceAllString(title, "")

	// 提取英文字母部分
	re2 := regexp.MustCompile(`[A-Za-z][A-Za-z\s\:\'\-\!\.]+`)
	matches := re2.FindAllString(title, -1)
	if len(matches) == 0 {
		return ""
	}
	// 取最长的英文片段作为片名
	longest := ""
	for _, m := range matches {
		m = strings.TrimSpace(m)
		if len(m) > len(longest) {
			longest = m
		}
	}
	return strings.TrimSpace(longest)
}

// 通过 IMDB Suggestion API 搜索 IMDB ID
func searchIMDB(title string, year string) string {
	// 清理标题用于搜索
	query := strings.ToLower(title)
	query = strings.ReplaceAll(query, " ", "_")
	query = strings.ReplaceAll(query, ":", "")
	query = strings.ReplaceAll(query, "'", "")
	query = strings.ReplaceAll(query, "-", "_")
	query = strings.ReplaceAll(query, ".", "")

	// 取第一个字母作为 suggestion API 的前缀
	if len(query) == 0 {
		return ""
	}
	firstChar := string(query[0])

	apiUrl := fmt.Sprintf("https://v2.sg.media-imdb.com/suggestion/%s/%s.json", firstChar, url.PathEscape(query))
	req, _ := http.NewRequest("GET", apiUrl, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var suggestion IMDBSuggestion
	if err := json.Unmarshal(body, &suggestion); err != nil {
		return ""
	}

	// 尝试匹配年份
	targetYear := 0
	if year != "" {
		targetYear, _ = strconv.Atoi(year)
	}

	titleLower := strings.ToLower(title)
	bestMatch := ""
	bestScore := 0

	for _, item := range suggestion.D {
		if item.ID == "" || !strings.HasPrefix(item.ID, "tt") {
			continue
		}

		score := 0
		itemTitleLower := strings.ToLower(item.L)

		// 标题相似度
		if itemTitleLower == titleLower {
			score += 100
		} else if strings.Contains(itemTitleLower, titleLower) || strings.Contains(titleLower, itemTitleLower) {
			score += 50
		}

		// 年份匹配
		if targetYear > 0 && item.Y == targetYear {
			score += 80
		} else if targetYear > 0 && abs(item.Y-targetYear) <= 1 {
			score += 30
		}

		if score > bestScore {
			bestScore = score
			bestMatch = item.ID
		}
	}

	if bestScore >= 50 {
		return bestMatch
	}
	return ""
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func printResult() {
	fmt.Println("\n--- 结果 ---")
	successCount := 0
	for i, movie := range movies {
		if movie == nil {
			continue
		}
		if movie.imdbId != "" {
			fmt.Printf("%d. [%s] IMDB: %s\n", i+1, movie.name, movie.imdbId)
			successCount++
		} else {
			fmt.Printf("%d. [%s] IMDB: N/A\n", i+1, movie.name)
		}
	}
	fmt.Printf("\n成功获取: %d/250\n", successCount)
}

func exportToCSV() {
	file, err := os.Create("top250.csv")
	if err != nil {
		fmt.Printf("创建 CSV 文件失败: %v\n", err)
		return
	}
	defer file.Close()

	file.WriteString("\xEF\xBB\xBF")

	w := csv.NewWriter(file)
	w.Write([]string{"排名", "电影名称", "豆瓣链接", "IMDB ID"})
	for i, movie := range movies {
		if movie == nil {
			continue
		}
		w.Write([]string{strconv.Itoa(i + 1), movie.name, movie.link, movie.imdbId})
	}
	w.Flush()

	if err := w.Error(); err != nil {
		fmt.Printf("写入 CSV 失败: %v\n", err)
		return
	}
	fmt.Println("\n✅ 已导出到 top250.csv")
}
