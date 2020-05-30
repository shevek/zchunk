#include <err.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

#include <zck.h>

struct chunk_stuff {
	zckChunk *chunk;
	size_t size;
};

static struct chunk_stuff
get_second_chunk(struct zckCtx * const zck, const size_t chunk_count)
{
	size_t idx = 0;
	zckChunk *chunk = zck_get_first_chunk(zck);
	if (chunk == NULL)
		errx(1, "zck_get_first_chunk() failed: %s", zck_get_error(zck));
	printf("got first chunk %p\n", chunk);

	size_t start = 0;
	for (size_t idx = 0; idx < chunk_count; idx++) {
		const ssize_t s_size = zck_get_chunk_size(chunk);
		if (s_size < 0)
			errx(1, "zck_get_chunk_size() returned invalid size %zd: %s", s_size, zck_get_error(zck));
		const size_t size = (size_t)s_size;
		printf("chunk %zu: start %zu size %zu\n", idx, start, size);

		if (size > 0 && start > 0) {
			printf("got it!\n");
			return (struct chunk_stuff){
				.chunk = chunk,
				.size = size,
			};
		}
		start += size;

		chunk = zck_get_next_chunk(chunk);
		if (chunk == NULL)
			errx(1, "get_next_chunk() failed for %zu: %s", idx + 1, zck_get_error(zck));
	}
	errx(1, "Could not find the second chunk!");
}

int main(const int argc, char * const argv[])
{
	if (argc != 3)
		errx(1, "Usage: chunk /path/to/file.zck /path/to/chunk.txt");

	const char * const src_name = argv[1];
	const int src_fd = open(src_name, O_RDONLY);
	if (src_fd == -1)
		err(1, "Could not open %s", src_name);

	struct zckCtx *zck = zck_create();
	if (zck == NULL)
		err(1, "zck_create() failed");
	printf("got zck context %p\n", zck);
	if (!zck_init_read(zck, src_fd))
		err(1, "zck_init_read() failed");

	const ssize_t header_len = zck_get_header_length(zck);
	if (header_len < 1)
		errx(1, "Invalid header length %zd", header_len);
	printf("header length %zd\n", header_len);
	const ssize_t s_chunk_count = zck_get_chunk_count(zck);
	if (s_chunk_count < 1)
		errx(1, "Invalid chunk count %zd", s_chunk_count);
	const size_t chunk_count = (size_t)s_chunk_count;
	printf("chunk count %zu\n", chunk_count);

	const struct chunk_stuff second = get_second_chunk(zck, chunk_count);
	printf("got second chunk %p size %zu\n", second.chunk, second.size);
	char * const data = malloc(second.size);
	if (data == NULL)
		err(1, "Could not allocate %zu bytes", second.size);
	const ssize_t nread = zck_get_chunk_data(second.chunk, data, second.size);
	if (nread != (ssize_t)second.size)
		errx(1, "zck_get_chunk_data() returned %zd: %s", nread, zck_get_error(zck));
	printf("got the data: %02x %02x %02x\n", data[0], data[1], data[2]);

	zck_free(&zck);
	if (zck != NULL)
		errx(1, "zck_free() did not zero the pointer");
	if (close(src_fd) == -1)
		err(1, "Could not close %s after reading", src_name);

	const char * const dst_name = argv[2];
	printf("About to write %zu bytes to %s\n", second.size, dst_name);
	const int dst_fd = open(dst_name, O_WRONLY | O_CREAT, 0644);
	if (dst_fd == -1)
		err(1, "Could not open %s for writing", dst_name);

	size_t nwritten = 0;
	while (nwritten < second.size) {
		printf("- %zu bytes left to write\n", second.size - nwritten);
		const ssize_t n = write(dst_fd, data + nwritten, second.size - nwritten);
		if (n < 1)
			err(1, "Could not write to %s", dst_name);
		printf("- wrote %zd bytes\n", n);
		nwritten += n;
	}
	if (close(dst_fd) == -1)
		err(1, "Could not close %s after writing", dst_name);
	printf("Whee!\n");
	return 0;
}
