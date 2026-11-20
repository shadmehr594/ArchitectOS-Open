from core.render.workflow_selector import WorkflowSelector


selector = WorkflowSelector()


tests = [

    {
        "engine":"flux",
        "mode":"text2img",
        "image":None
    },


    {
        "engine":"flux",
        "mode":"img2img",
        "image":{
            "filename":"test.png"
        }
    },


    {
        "engine":"wan",
        "mode":"i2v",
        "image":{
            "filename":"test.png"
        }
    }

]


for t in tests:

    print(
        t,
        "=>",
        selector.select(t)
    )