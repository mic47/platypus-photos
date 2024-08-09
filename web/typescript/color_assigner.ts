export class ColorAssigner {
    private sortedColors: Array<{ hue: number; label: string }> = [];
    private byLabel: { [label: string]: number } = {};
    private fixedLabels: Set<string> = new Set();
    constructor(fixed: Array<{ hue: number; label: string }>) {
        fixed.forEach((item) => {
            this.byLabel[item.label] = item.hue;
            this.sortedColors.push(item);
            this.fixedLabels.add(item.label);
        });
        this.sortedColors.sort((a, b) => {
            if (a.hue < b.hue) {
                return -1;
            }
            if (a.hue > b.hue) {
                return 1;
            }
            return 0;
        });
    }
    get_hue(label: string): number {
        const value = this.byLabel[label];
        if (value !== undefined) {
            return value;
        }
        return this.add(label);
    }
    get_str(label: string): string {
        const hue = this.get_hue(label);
        return `hsl(${hue}, 100%, 50%)`;
    }
    remove(label: string) {
        if (this.fixedLabels.has(label)) {
            return;
        }
        if (this.byLabel[label] !== undefined) {
            delete this.byLabel[label];
        }
        this.sortedColors = this.sortedColors.filter((x) => x.label != label);
    }
    private add(label: string): number {
        if (this.sortedColors.length === 0) {
            const hue = 180;
            this.sortedColors.push({ hue, label });
            this.byLabel[label] = hue;
            return hue;
        }
        const initial_width =
            360 -
            this.sortedColors[this.sortedColors.length - 1].hue +
            this.sortedColors[0].hue;
        let initial_hue = this.sortedColors[0].hue - initial_width / 2;
        let index = 0;
        if (initial_hue < 0) {
            // Wrap around 360.
            initial_hue = 360 + initial_hue;
            index = this.sortedColors.length;
        }
        let center: {
            width: number;
            hue: number;
        } = {
            width: initial_width,
            hue: initial_hue,
        };
        for (let i = 0; i < this.sortedColors.length - 1; i++) {
            const width =
                this.sortedColors[i + 1].hue - this.sortedColors[i].hue;
            if (width > center.width) {
                index = i + 1;
                center = {
                    width,
                    hue: this.sortedColors[i].hue + width / 2,
                };
            }
        }
        this.byLabel[label] = center.hue;
        this.sortedColors.splice(index, 0, { hue: center.hue, label });
        return center.hue;
    }
}
