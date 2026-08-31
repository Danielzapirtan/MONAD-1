#include <stdio.h>
#include <stdlib.h>

int conv_by_line() {
	while (!feof(stdin)) {
		int ch = getchar();
		if (ch == 10) {
			putchar(10);
			system("echo -n $(date +%Y%m%d%H%M%S%N)'\t'");
			fflush(stdout);
		} else if (ch != EOF) {
			putchar(ch);
		}
	}
}

int main() {conv_by_line();}
