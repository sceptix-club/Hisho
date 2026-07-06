<script lang="ts">
	import { cn } from '$lib/utils.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Field from '$lib/components/ui/field/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import type { HTMLAttributes } from 'svelte/elements';

	let { class: className, ...restProps }: HTMLAttributes<HTMLDivElement> = $props();
</script>

<div class={cn('flex flex-col gap-6', className)} {...restProps}>
	<form>
		<Field.Group>
			<div class="flex flex-col items-center gap-2 text-center">
				<h1 class="text-xl font-bold">Hisho</h1>
				<Field.Description>
					Already have an account? <a href="/login">login</a>
				</Field.Description>
			</div>
			<Field.Field>
				<Button type="submit">Create Account</Button>
			</Field.Field>
			<Field.Separator>Or</Field.Separator>
			<Field.Field class="grid gap-4">
				<Button variant="outline" type="button">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
						<path
							d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
							fill="currentColor"
						/>
					</svg>
					Continue with Google
				</Button>
			</Field.Field>
		</Field.Group>
	</form>

	<Field.Description class="px-6 text-center">
		Made with love by <a href="https://www.sceptix.in/">The Sceptix Club</a>
	</Field.Description>
</div>
