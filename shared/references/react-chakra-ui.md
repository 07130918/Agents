# Chakra UI v3 実装ガイド

## v2 → v3 破壊的変更一覧

### Boolean Props の変更 (最頻出バグ)

| v2 (旧) | v3 (新) |
|---------|---------|
| `isDisabled` | `disabled` |
| `isLoading` | `loading` |
| `isOpen` | `open` |
| `isReadOnly` | `readOnly` |
| `isRequired` | `required` |
| `isInvalid` | `invalid` |
| `isChecked` | `checked` |
| `isFocused` | `focused` |
| `isFullWidth` | `width="full"` |
| `isAttached` | `attached` |
| `spacing` | `gap` |

### カラーシステムの変更

- `colorScheme` → `colorPalette`
- `color="blue.500"` は変更なし

---

## Dialog / Modal

### v3 の Dialog 実装

```tsx
import {
  DialogRoot,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseTrigger,
  DialogBackdrop,
} from '@/components/ui/dialog'

// ✅ v3 正しい実装
<DialogRoot open={isOpen} onOpenChange={(e) => setIsOpen(e.open)}>
  <DialogBackdrop />
  <DialogContent>
    <DialogHeader>タイトル</DialogHeader>
    <DialogBody>コンテンツ</DialogBody>
    <DialogFooter>
      <Button onClick={onClose}>閉じる</Button>
    </DialogFooter>
    <DialogCloseTrigger />
  </DialogContent>
</DialogRoot>
```

### ❌ よくある間違い

```tsx
// v2の書き方 - v3では動かない
<Modal isOpen={isOpen} onClose={onClose}>
  <ModalOverlay />
  <ModalContent>...</ModalContent>
</Modal>
```

---

## Stack / HStack / VStack

```tsx
// ✅ Stack (垂直方向がデフォルト)
<Stack gap={4}>
  <Box>アイテム1</Box>
  <Box>アイテム2</Box>
</Stack>

// ✅ HStack (水平方向)
<HStack gap={4} align="center">
  <Icon />
  <Text>ラベル</Text>
</HStack>

// ✅ 方向指定
<Stack direction="row" gap={4}>   {/* HStack と同等 */}
  ...
</Stack>
```

---

## Button

```tsx
// ✅ v3 正しい実装
<Button
  loading={isLoading}
  disabled={isDisabled}
  colorPalette="blue"
  variant="solid"
>
  送信
</Button>

// ✅ アイコン付き
<Button>
  <Icon as={AddIcon} />
  追加
</Button>
```

---

## Form / Input / Field

```tsx
// ✅ フォームフィールド (v3)
<Field label="ユーザー名" invalid={!!errors.name} errorText={errors.name?.message}>
  <Input
    {...register('name')}
    readOnly={isReadOnly}
  />
</Field>
```

---

## Select

```tsx
import { SelectRoot, SelectTrigger, SelectContent, SelectItem, SelectValueText } from '@/components/ui/select'

// ✅ v3 の Select
<SelectRoot value={[value]} onValueChange={(e) => setValue(e.value[0])}>
  <SelectTrigger>
    <SelectValueText placeholder="選択してください" />
  </SelectTrigger>
  <SelectContent>
    <SelectItem item={{ value: 'option1', label: 'オプション1' }}>オプション1</SelectItem>
  </SelectContent>
</SelectRoot>
```

---

## よくある TypeScript エラー

```tsx
// ❌ エラー: Property 'isDisabled' does not exist
<Button isDisabled={true}>

// ✅ 正しい
<Button disabled={true}>

// ❌ エラー: Property 'colorScheme' does not exist
<Button colorScheme="blue">

// ✅ 正しい
<Button colorPalette="blue">

// ❌ エラー: Property 'spacing' does not exist on type 'StackProps'
<Stack spacing={4}>

// ✅ 正しい
<Stack gap={4}>
```

---

## カスタムレシピ (テーマ拡張)

```tsx
// ✅ v3 のカスタムレシピ
import { defineRecipe } from "@chakra-ui/react"

const buttonRecipe = defineRecipe({
  variants: {
    visual: {
      primary: { bg: "blue.500", color: "white" },
      danger: { bg: "red.500", color: "white" },
    },
  },
})
```

---

## パフォーマンス注意点

- `chakra()` ファクトリー関数は必要時のみ使用
- 頻繁に更新されるコンポーネントには `React.memo` を使用
- 大量リスト表示時は仮想化 (react-virtual等) を検討
