exports.verify = function (context, expect) {
    var rootNode = context.rootNode;
    var selectNode = rootNode.querySelector('select');
    expect(selectNode.selectedIndex).to.equal(2);
    expect(selectNode.children[2].selected).to.equal(true);
};
