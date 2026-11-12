/**
 * Form states shared by Input, Textarea and NumberInput.
 * 오류 테두리는 필드 자신의 aria-invalid뿐 아니라, FormHelper 래퍼(`group/field`)의
 * aria-invalid에도 반응한다. (chakra FormControl isInvalid 전파와 동일한 동작)
 */
export const fieldBaseStyles =
  "w-full bg-background text-style-pre-body-06 text-text-secondary shadow-none outline-none transition-colors placeholder:text-text-quaternary disabled:cursor-not-allowed disabled:opacity-40 aria-[invalid=true]:border-support-error aria-[invalid=true]:focus:border-support-error group-aria-[invalid=true]/field:border-support-error group-aria-[invalid=true]/field:focus:border-support-error";
export const outlinedFieldStyles =
  "border border-solid border-border-tertiary focus:border-2 focus:border-border-secondary read-only:border-border-quaternary read-only:focus:border read-only:focus:border-border-quaternary";
