package main

import (
	"fmt"

	"github.com/google/uuid"
	"github.com/pkg/errors"
	"golang.org/x/text/language"
)

//vulnerable dependency is golang.org/x/text v0.3.7

func main() {
	fmt.Println(uuid.New(), errors.New("x"), language.English)
}