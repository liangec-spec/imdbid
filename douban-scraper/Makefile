.PHONY: setup
setup:
	@go mod tidy
	
.PHONY: lint
lint:
	@goimports -w *.go
	
.PHONY: run
run:
	@go run main.go
