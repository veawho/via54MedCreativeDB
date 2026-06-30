// via54_rag_go — TF-IDF RAG Search Engine in Go
// Pure Go + CGO-free SQLite (github.com/mattn/go-sqlite3 with system libsqlite3)
package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

// ── Config ──────────────────────────────────────────────
var dbPath = "G:/agent/ai/projects/via54ADIdeahub/via54_rag/vector.db"

// ── In-memory index ─────────────────────────────────────
type chunk struct {
	id     int64
	docID  int64
	text   string
	tokens []string
	tf     map[string]float64
}

type docMeta struct {
	id        int64
	filename  string
	title     string
	sourceURL string
}

type index struct {
	chunks      map[int64]*chunk      // chunkID -> chunk
	chunksByDoc map[int64][]*chunk   // docID -> chunks
	docs       map[int64]*docMeta    // docID -> meta
	inverted   map[string][]int64    // term -> chunkIDs
	idf        map[string]float64   // term -> IDF
	N          int                   // total docs
}

var idx *index

// ── Tokenizer ───────────────────────────────────────────
func isChinese(r rune) bool {
	return r >= 0x4e00 && r <= 0x9fff
}

// extractCN extracts consecutive Chinese character sequences
func extractCNSequences(text string) []string {
	var seqs []string
	var current []rune
	for _, r := range text {
		if isChinese(r) {
			current = append(current, r)
		} else {
			if len(current) > 0 {
				seqs = append(seqs, string(current))
				current = nil
			}
		}
	}
	if len(current) > 0 {
		seqs = append(seqs, string(current))
	}
	return seqs
}

func tokenize(text string) []string {
	text = strings.ToLower(text)
	var tokens []string

	enTokens := regexp.MustCompile(`[a-z0-9]+`).FindAllString(text, -1)
	tokens = append(tokens, enTokens...)

	// Chinese bigram + trigram
	cnSeqs := extractCNSequences(text)
	for _, seq := range cnSeqs {
		if len(seq) < 2 {
			continue
		}
		runes := []rune(seq)
		for i := 0; i < len(runes); i++ {
			for _, n := range []int{2, 3} {
				if i+n <= len(runes) {
					tokens = append(tokens, string(runes[i:i+n]))
				}
			}
		}
	}

	stopwords := map[string]bool{
		"的": true, "了": true, "在": true, "是": true, "我": true, "有": true,
		"和": true, "就": true, "不": true, "人": true, "都": true, "一": true,
		"上": true, "也": true, "很": true, "到": true, "说": true, "要": true,
		"去": true, "你": true, "会": true, "着": true, "看": true, "好": true,
		"这": true, "那": true, "它": true, "他": true, "她": true, "们": true,
		"中": true, "为": true, "与": true, "但": true, "或": true, "以": true,
		"而": true, "及": true, "等": true, "其": true, "被": true, "把": true,
		"给": true, "让": true, "从": true, "用": true, "对": true, "于": true,
	}

	var filtered []string
	for _, t := range tokens {
		if len(t) >= 2 && !stopwords[t] {
			filtered = append(filtered, t)
		}
	}
	return filtered
}

func computeTF(tokens []string) map[string]float64 {
	if len(tokens) == 0 {
		return nil
	}
	freq := make(map[string]int)
	for _, t := range tokens {
		freq[t]++
	}
	tf := make(map[string]float64)
	for t, c := range freq {
		tf[t] = float64(c) / float64(len(tokens))
	}
	return tf
}

// ── Load index from SQLite ───────────────────────────────
func loadIndex() error {
	idx = &index{
		chunks:      make(map[int64]*chunk),
		chunksByDoc: make(map[int64][]*chunk),
		docs:        make(map[int64]*docMeta),
		inverted:    make(map[string][]int64),
		idf:         make(map[string]float64),
	}

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	// Load doc_meta
	rows, err := db.Query("SELECT id, filename, title, COALESCE(source_url,'') FROM doc_meta")
	if err != nil {
		return fmt.Errorf("query doc_meta: %w", err)
	}
	for rows.Next() {
		var m docMeta
		if err := rows.Scan(&m.id, &m.filename, &m.title, &m.sourceURL); err != nil {
			continue
		}
		idx.docs[m.id] = &m
	}
	rows.Close()
	idx.N = len(idx.docs)

	if idx.N == 0 {
		log.Println("⚠️  No documents in DB")
		return nil
	}

	// Load chunks
	chunkRows, err := db.Query("SELECT id, doc_id, text, tokens FROM chunks")
	if err != nil {
		return fmt.Errorf("query chunks: %w", err)
	}
	for chunkRows.Next() {
		var c chunk
		var text, tokensJSON string
		if err := chunkRows.Scan(&c.id, &c.docID, &text, &tokensJSON); err != nil {
			continue
		}
		c.text = text
		var tokens []string
		if err := json.Unmarshal([]byte(tokensJSON), &tokens); err != nil {
			continue
		}
		c.tokens = tokens
		c.tf = computeTF(tokens)
		idx.chunks[c.id] = &c
		if idx.chunksByDoc[c.docID] == nil {
			idx.chunksByDoc[c.docID] = []*chunk{}
		}
		idx.chunksByDoc[c.docID] = append(idx.chunksByDoc[c.docID], &c)
	}
	chunkRows.Close()

	// Load IDF (doc_count) and compute real IDF
	N := float64(idx.N)
	idfRows, err := db.Query("SELECT term, doc_count FROM idf")
	if err != nil {
		return fmt.Errorf("query idf: %w", err)
	}
	for idfRows.Next() {
		var term string
		var docCount int
		if err := idfRows.Scan(&term, &docCount); err != nil {
			continue
		}
		// idf = log(N / (dc+1)) + 1
		idf := math.Log(N/(float64(docCount)+1)) + 1
		idx.idf[term] = idf
	}
	idfRows.Close()

	// Load inverted index
	invRows, err := db.Query("SELECT term, chunk_id FROM inverted")
	if err != nil {
		return fmt.Errorf("query inverted: %w", err)
	}
	for invRows.Next() {
		var term string
		var chunkID int64
		if err := invRows.Scan(&term, &chunkID); err != nil {
			continue
		}
		idx.inverted[term] = append(idx.inverted[term], chunkID)
	}
	invRows.Close()

	log.Printf("✅ Index loaded: %d docs, %d chunks, %d terms",
		idx.N, len(idx.chunks), len(idx.idf))
	return nil
}

// ── Search ───────────────────────────────────────────────
type searchResult struct {
	Score  float64 `json:"score"`
	Text   string  `json:"text"`
	Doc    string  `json:"doc"`
	Title  string  `json:"title"`
	Source string  `json:"source,omitempty"`
}

func cosine(qTokens []string, qTF map[string]float64) []*searchResult {
	if len(qTokens) == 0 || idx.N == 0 {
		return nil
	}

	// Collect relevant chunk IDs
	chunkSet := make(map[int64]bool)
	for _, term := range qTokens {
		if ids, ok := idx.inverted[term]; ok {
			for _, id := range ids {
				chunkSet[id] = true
			}
		}
	}
	if len(chunkSet) == 0 {
		return nil
	}

	// Compute q_norm with IDF
	qNorm := 0.0
	for term, qval := range qTF {
		idf := idx.idf[term]
		qNorm += (qval * idf) * (qval * idf)
	}
	qNorm = math.Sqrt(qNorm)
	if qNorm == 0 {
		return nil
	}

	var scored []*searchResult
	for cid := range chunkSet {
		c := idx.chunks[cid]
		if c == nil || c.tf == nil {
			continue
		}

		// Common terms
		var commonTerms []string
		for term := range qTF {
			if _, ok := c.tf[term]; ok {
				commonTerms = append(commonTerms, term)
			}
		}
		if len(commonTerms) == 0 {
			continue
		}

		// dot = sum(q_tfidf * d_tfidf)
		dot := 0.0
		for _, term := range commonTerms {
			idf := idx.idf[term]
			dot += qTF[term] * idf * c.tf[term] * idf
		}

		// d_norm
		dNorm := 0.0
		for term, dval := range c.tf {
			idf := idx.idf[term]
			dNorm += (dval * idf) * (dval * idf)
		}
		dNorm = math.Sqrt(dNorm)
		if dNorm == 0 {
			continue
		}

		score := dot / (qNorm * dNorm)
		meta := idx.docs[c.docID]
		title, filename := "", ""
		if meta != nil {
			title = meta.title
			filename = meta.filename
		}

		scored = append(scored, &searchResult{
			Score: math.Round(score*10000) / 10000,
			Text:  c.text,
			Doc:   filename,
			Title: title,
		})
	}

	sort.Slice(scored, func(i, j int) bool {
		return scored[i].Score > scored[j].Score
	})
	return scored
}

func search(query string, topK int) []*searchResult {
	qTokens := tokenize(query)
	if len(qTokens) == 0 {
		return nil
	}
	qTF := computeTF(qTokens)
	results := cosine(qTokens, qTF)
	if results == nil {
		return nil
	}
	if topK > 0 && len(results) > topK {
		return results[:topK]
	}
	return results
}

// ── HTTP Server ─────────────────────────────────────────
func serveHTTP(port int) {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/search", func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("q")
		if query == "" {
			http.Error(w, "missing q param", 400)
			return
		}
		results := search(query, 5)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(results)
	})

	mux.HandleFunc("/reload", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST only", 405)
			return
		}
		log.Println("🔄 Reloading index...")
		if err := loadIndex(); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		w.Write([]byte("OK"))
	})

	addr := fmt.Sprintf("127.0.0.1:%d", port)
	log.Printf("📡 HTTP server: http://%s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}

// ── CLI ─────────────────────────────────────────────────
func main() {
	args := os.Args
	if len(args) < 2 {
		// Default: build + serve
		if err := loadIndex(); err != nil {
			log.Fatal(err)
		}
		serveHTTP(18766)
		return
	}

	switch args[1] {
	case "build":
		fmt.Println("🔨 Loading index...")
		if err := loadIndex(); err != nil {
			log.Fatal(err)
		}
		fmt.Println("✅ Done")

	case "search":
		if len(args) < 3 {
			fmt.Println("Usage: via54_rag_go search <query>")
			return
		}
		query := strings.Join(args[2:], " ")
		if err := loadIndex(); err != nil {
			log.Fatal(err)
		}
		results := search(query, 5)
		fmt.Printf("\n🔍 Query: %s\n", query)
		if len(results) == 0 {
			fmt.Println("  No results")
			return
		}
		for i, r := range results {
			title := r.Title
			if title == "" {
				title = r.Doc
			}
			text := r.Text
			if len(text) > 100 {
				text = text[:100] + "..."
			}
			fmt.Printf("\n[%d] %s (score=%.4f)\n   %s\n", i+1, title, r.Score, text)
		}

	case "serve":
		if err := loadIndex(); err != nil {
			log.Fatal(err)
		}
		serveHTTP(18766)

	default:
		fmt.Printf("Unknown command: %s\n", args[1])
		fmt.Println("Usage: via54_rag_go [build|search|serve]")
	}
}
